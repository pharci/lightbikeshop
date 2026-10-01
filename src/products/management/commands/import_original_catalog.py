import json
import ssl
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID

import certifi

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from unidecode import unidecode

from products.brands import normalize_brand_title
from products.catalog_enrichment import apply_characteristics, extract_characteristics, extract_description_characteristics
from products.models import Attribute, AttributeValue, Brand, Category, CategoryAttribute, Image, Product, Variant


SINGULAR = {
    "Валы": "Вал", "Вилки": "Вилка", "Втулки": "Втулка", "Выносы": "Вынос",
    "Джинсы": "Джинсы", "Звезды": "Звезда", "Инструменты": "Инструмент",
    "Камеры": "Камера", "Каретки": "Каретка", "Колеса": "Колесо", "Обода": "Обод",
    "Ободные ленты": "Ободная лента", "Педали": "Педали", "Пеги": "Пега",
    "Перчатки": "Перчатки", "Покрышки": "Покрышка", "Рамы": "Рама",
    "Рулевые": "Рулевая", "Рули": "Руль", "Сидения": "Седло", "Спицы": "Спицы",
    "Титановые болты": "Титановый болт", "Тормоза": "Тормоз", "Шатуны": "Система шатунов",
}


def unique_slug(model, title):
    max_len = model._meta.get_field("slug").max_length
    base = (slugify(unidecode(title)) or "item")[:max_len]
    candidate, number = base, 2
    while model.objects.filter(slug=candidate).exists():
        suffix = f"-{number}"
        candidate = f"{base[:max_len-len(suffix)]}{suffix}"
        number += 1
    return candidate


class Command(BaseCommand):
    help = "Импортирует полный каталог с оригинального LightBikeShop в локальную базу"

    def add_arguments(self, parser):
        parser.add_argument("directory", type=Path)
        parser.add_argument("--skip-images", action="store_true")

    def handle(self, *args, **options):
        directory = options["directory"].expanduser().resolve()
        product_files = sorted(directory.glob("products_*.json"))
        variant_file = directory / "variants_complete.json"
        if not product_files or not variant_file.exists():
            raise CommandError("Нет полного экспорта products_*.json/variants_complete.json")
        products = [row for path in product_files for row in json.loads(path.read_text())]
        variants = json.loads(variant_file.read_text())
        by_id = {row["id"]: row for row in variants}
        expected = {row["id"] for product in products for row in product["variants"]}
        if len(products) != 77 or len(by_id) != 200 or set(by_id) != expected:
            raise CommandError(
                f"Неполный экспорт: товаров {len(products)}, вариантов {len(by_id)}, "
                f"пропущено {len(expected - set(by_id))}"
            )

        root, _ = Category.objects.get_or_create(
            title="BMX", defaults={"title_plural": "BMX", "title_singular": "BMX", "slug": "bmx"}
        )
        categories = {}
        for title in sorted({row["category"].strip() for row in products}):
            category = Category.objects.filter(title__iexact=title).first()
            if not category:
                category = Category.objects.create(
                    title=title, title_plural=title, title_singular=SINGULAR.get(title, title),
                    slug=unique_slug(Category, title), parent=root,
                )
            else:
                changed = []
                if category.pk != root.pk and category.parent_id != root.pk:
                    category.parent = root
                    changed.append("parent")
                if not category.title_singular:
                    category.title_singular = SINGULAR.get(title, title)
                    changed.append("title_singular")
                if changed:
                    category.save(update_fields=changed)
            categories[title] = category

        image_jobs = []
        with transaction.atomic():
            for row in products:
                brand = self._brand(row.get("brand"))
                product, _ = Product.objects.update_or_create(
                    pk=UUID(row["id"]),
                    defaults={
                        "base_name": row.get("name", "").strip(),
                        "category": categories[row["category"].strip()],
                        "brand": brand,
                        "description": row.get("description") or "",
                        "weight": int(row["weight"]) if str(row.get("weight") or "").isdigit() else None,
                    },
                )
                rows = [by_id[item["id"]] for item in row["variants"]]
                changing_names = self._changing_names(rows)
                for variant_row in rows:
                    old_price = Decimal(variant_row.get("old_price") or 0)
                    variant, _ = Variant.objects.update_or_create(
                        pk=UUID(variant_row["id"]),
                        defaults={
                            "product": product,
                            "seller_article": variant_row.get("seller_article") or None,
                            "ozon_article": variant_row.get("ozon_article") or None,
                            "wb_article": variant_row.get("wb_article") or None,
                            "price": Decimal(variant_row["price"]),
                            "old_price": old_price if old_price > 0 else None,
                            "inventory": int(variant_row.get("inventory") or 0),
                            "fulfillment_type": Variant.FulfillmentType.STOCK,
                            "sales_unit": self._sales_unit(product),
                            "new": bool(variant_row.get("new")),
                            "rec": bool(variant_row.get("rec")),
                            "is_active": bool(variant_row.get("is_active", True)),
                        },
                    )
                    self._explicit_attributes(product, variant, variant_row, changing_names)
                    common = {
                        "Тип товара": product.category.title_singular or product.category.title,
                        "Единица продажи": "Пара" if variant.sales_unit == Variant.SalesUnit.PAIR else "Штука",
                        **extract_characteristics(product.base_name, product.description),
                        **extract_description_characteristics(product.description),
                    }
                    apply_characteristics(product, variant, common, variant_names=())
                    variant.save()
                    image_jobs.extend((variant, url, sort) for sort, url in enumerate(variant_row.get("images") or []))

            # История локальных тестовых заказов должна оставаться доступной.
            Variant.objects.filter(
                seller_article__startswith="demo:", order_items__isnull=True,
            ).delete()
            Product.objects.filter(variants__isnull=True).delete()

        downloaded, failed = 0, []
        if not options["skip_images"]:
            context = ssl.create_default_context(cafile=certifi.where())
            for index, (variant, url, sort) in enumerate(image_jobs, 1):
                filename = Path(urlparse(url).path).name
                if variant.images.filter(image__endswith=filename).exists():
                    continue
                try:
                    request = Request(url, headers={"User-Agent": "Mozilla/5.0 LightBikeShop catalog import"})
                    with urlopen(request, timeout=20, context=context) as response:
                        content = response.read()
                    image = Image(variant=variant, alt=variant.display_name(), sort=sort)
                    image.image.save(filename, ContentFile(content), save=True)
                    downloaded += 1
                except Exception as exc:
                    failed.append((url, str(exc)))
                if index % 50 == 0:
                    self.stdout.write(f"Фото: {index}/{len(image_jobs)}")

        self.stdout.write(self.style.SUCCESS(
            f"Импортировано: {len(products)} товаров, {len(by_id)} вариантов; "
            f"скачано фото: {downloaded}; ошибок фото: {len(failed)}"
        ))
        for url, error in failed[:10]:
            self.stderr.write(f"{url}: {error}")

    @staticmethod
    def _brand(raw_title):
        title = normalize_brand_title(raw_title)
        if not title or title == "---------":
            return None
        brand = Brand.objects.filter(title__iexact=title).first()
        if brand:
            return brand
        return Brand.objects.create(title=title, slug=unique_slug(Brand, title))

    @staticmethod
    def _changing_names(rows):
        values = defaultdict(set)
        for row in rows:
            for item in row.get("attrs") or []:
                value = item.get("text") or item.get("number")
                if value not in (None, ""):
                    values[item["name"]].add(str(value))
        return {name for name, choices in values.items() if len(choices) > 1}

    @staticmethod
    def _sales_unit(product):
        text = f"{product.category.title} {product.base_name} {product.description}".lower()
        if product.category.title in {"Педали", "Перчатки"} or "пара" in text:
            return Variant.SalesUnit.PAIR
        return Variant.SalesUnit.PIECE

    @staticmethod
    def _explicit_attributes(product, variant, row, changing_names):
        for item in row.get("attrs") or []:
            name = (item.get("name") or "").strip()
            text, number = item.get("text") or "", item.get("number") or ""
            raw_boolean = item.get("bool")
            boolean = raw_boolean if isinstance(raw_boolean, bool) else None
            if not name or (not text and not number and boolean is None):
                if name:
                    attribute = Attribute.objects.filter(name=name).first()
                    if attribute:
                        AttributeValue.objects.filter(variant=variant, attribute=attribute).delete()
                continue
            suggested = Attribute.NUMBER if number else Attribute.BOOL if boolean is not None else Attribute.TEXT
            attribute, _ = Attribute.objects.get_or_create(
                name=name, defaults={"slug": unique_slug(Attribute, name), "value_type": suggested}
            )
            is_variant = name in changing_names
            usage, _ = CategoryAttribute.objects.get_or_create(
                category=product.category, attribute=attribute,
                defaults={"is_filterable": True, "is_variant": is_variant, "sort_order": 100},
            )
            if is_variant and not usage.is_variant:
                usage.is_variant = True
                usage.save(update_fields=["is_variant"])
            defaults = {"value_text": "", "value_number": None, "value_bool": None}
            if attribute.value_type == Attribute.NUMBER and number:
                defaults["value_number"] = Decimal(number)
            elif attribute.value_type == Attribute.BOOL and boolean is not None:
                defaults["value_bool"] = bool(boolean)
            else:
                defaults["value_text"] = str(text or number or ("Да" if boolean else "Нет"))[:255]
            AttributeValue.objects.update_or_create(variant=variant, attribute=attribute, defaults=defaults)
