import hashlib
import math
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import close_old_connections, transaction
from django.utils.text import slugify

from products.brands import normalize_brand_title
from products.catalog_enrichment import apply_characteristics, extract_characteristics, taobao_item_id
from products.models import Brand, Category, Image, Product, TaobaoImportItem, Variant


class Command(BaseCommand):
    help = "Автоматически публикует видимые товары локального парсера как предзаказ"

    def add_arguments(self, parser):
        parser.add_argument("--watch", action="store_true")
        parser.add_argument("--interval", type=int, default=60)

    def handle(self, *args, **options):
        while True:
            try:
                count = self.sync()
                self.stdout.write(f"Синхронизировано предзаказов: {count}")
            except Exception as exc:
                self.stderr.write(f"Ошибка синхронизации: {exc}")
            if not options["watch"]:
                break
            close_old_connections()
            time.sleep(max(15, options["interval"]))

    def sync(self):
        parser_url = settings.TAOBAO_PARSER_URL.rstrip("/")
        products_response = requests.get(f"{parser_url}/api/products", timeout=30)
        products_response.raise_for_status()
        products = products_response.json()
        pricing_response = requests.get(f"{parser_url}/api/pricing", timeout=10)
        pricing_response.raise_for_status()
        pricing = pricing_response.json()
        rate = float(pricing["cbr_rate"]) + float(pricing["surcharge_rub"])
        markup = 1 + float(pricing["markup_percent"]) / 100
        root, _ = Category.objects.get_or_create(title="BMX", defaults={"title_plural": "BMX", "title_singular": "BMX", "slug": "bmx"})
        seen = set()
        synced = 0
        for item in products:
            if item.get("hidden"):
                continue
            source_key = f"{item.get('store')}:{item.get('external_id')}"
            seen.add(source_key)
            title = (item.get("title_ru") or item.get("title") or "Товар").strip()
            brand_title = normalize_brand_title(
                item.get("brand") or item.get("store") or "Предзаказ"
            )[:100]
            category_title = self.infer_category((item.get("category") or "").strip(), title)
            category, _ = Category.objects.get_or_create(
                title=category_title,
                defaults={"parent": root, "title_plural": category_title, "title_singular": self.singular(category_title), "slug": self.unique_category_slug(root, category_title)},
            )
            brand, _ = Brand.objects.get_or_create(slug=slugify(brand_title)[:190] or "taobao", defaults={"title": brand_title, "image": ""})
            cny = float(item.get("price_cny") or 0)
            raw_price = cny * rate * markup
            price = max(90, math.ceil((raw_price - 90) / 100) * 100 + 90)
            article = "taobao:" + hashlib.sha1(source_key.encode()).hexdigest()[:32]
            base_name = self.clean_name(title, brand_title, category_title)
            with transaction.atomic():
                draft, _ = TaobaoImportItem.objects.update_or_create(
                    source_key=source_key,
                    defaults={"store": item.get("store", ""), "external_id": item.get("external_id", ""), "title_original": item.get("title", ""), "title_ru": title, "description_ru": item.get("description_ru", ""), "category_name": category_title, "brand_name": brand_title, "variant_name": item.get("variant", ""), "price_cny": cny, "price_rub": price, "available": bool(item.get("available")), "image_url": item.get("image_url", ""), "product_url": item.get("url", ""), "raw": item},
                )
                variant = Variant.objects.filter(seller_article=article).select_related("product").first()
                if variant:
                    product = variant.product
                    product.base_name, product.category, product.brand = base_name, category, brand
                    product.description = item.get("description_ru", "")
                    product.save()
                else:
                    parent_id = taobao_item_id(item.get("external_id", ""))
                    sibling = TaobaoImportItem.objects.filter(
                        store=item.get("store", ""),
                        external_id__startswith=parent_id,
                        product__isnull=False,
                    ).select_related("product").first() if parent_id else None
                    product = sibling.product if sibling else Product.objects.create(
                        base_name=base_name,
                        category=category,
                        brand=brand,
                        description=item.get("description_ru", ""),
                    )
                    variant = Variant(product=product, seller_article=article)
                variant.price = price
                variant.inventory = 0
                variant.fulfillment_type = Variant.FulfillmentType.PREORDER
                variant.preorder_days_min, variant.preorder_days_max = 30, 45
                unit_text = " ".join(str(item.get(k, "")) for k in ("title", "title_ru", "variant")).lower()
                variant.sales_unit = Variant.SalesUnit.PAIR if category_title in ("Педали", "Грипсы") or any(x in unit_text for x in ("一对", "пара", "pair")) else Variant.SalesUnit.PIECE
                variant.is_active = bool(item.get("available"))
                variant.save()
                draft.product, draft.variant, draft.status = product, variant, TaobaoImportItem.Status.IMPORTED
                draft.save(update_fields=["product", "variant", "status"])
                common_specs = extract_characteristics(
                    title, item.get("title", ""), item.get("description_ru", "")
                )
                variant_specs = extract_characteristics(item.get("variant", ""))
                specs = {
                    "Тип товара": category.title_singular or category.title,
                    "Единица продажи": "Пара" if variant.sales_unit == Variant.SalesUnit.PAIR else "Штука",
                    **common_specs,
                    **variant_specs,
                }
                apply_characteristics(product, variant, specs, variant_names=variant_specs.keys())
            self.download_image(variant, brand, item.get("image_url", ""), title)
            synced += 1
        Variant.objects.filter(taobao_imports__isnull=False, fulfillment_type="preorder").exclude(taobao_imports__source_key__in=seen).update(is_active=False)
        return synced

    def infer_category(self, category, title):
        if category:
            return category[:50]
        value = title.lower()
        rules = (("Грипсы", ("грипс", "ручк", "grip")), ("Каретки", ("mid bb", "каретк")), ("Пеги", ("проушин", "пег", "peg")), ("Рулевые", ("набор чаш", "набор мисок", "рулевая")))
        for name, words in rules:
            if any(word in value for word in words):
                return name
        return "Прочее"

    def singular(self, category):
        return {"Вилки":"Вилка", "Втулки":"Втулка", "Выносы":"Вынос", "Звезды":"Звезда", "Обода":"Обод", "Пеги":"Пега", "Педали":"Педали", "Покрышки":"Покрышка", "Рамы":"Рама", "Рулевые":"Рулевая", "Рули":"Руль", "Сидения":"Седло", "Шатуны":"Система шатунов", "Грипсы":"Грипсы", "Каретки":"Каретка"}.get(category, category)

    def clean_name(self, title, brand, category):
        value = re.sub(r"\s+", " ", title).strip(" -,.[]")
        if brand:
            value = re.sub(rf"^(?:{re.escape(brand)}\s*)+", "", value, flags=re.I)
        terms = {
            "Вилки": r"\b(?:передн(?:яя|ей)\s+)?вилк[аиуы]?\b",
            "Втулки": r"\b(?:передняя|задняя|свободная)?\s*втулк[аиуы]?\b",
            "Выносы": r"\b(?:вынос|стебель|шток)\b",
            "Звезды": r"\bзв[её]здочк[аиуы]?\b",
            "Обода": r"\bобод[аы]?\b",
            "Пеги": r"\b(?:пега|пеги|базука|ракетная установка)\b",
            "Рамы": r"\b(?:рама|рамка|корпус)\b",
            "Рули": r"\bрул(?:ь|я)\b",
            "Сидения": r"\b(?:седло|сиденье)\b",
            "Шатуны": r"\b(?:шатун(?:ы|ыы)?|рукоятка|crank)\b",
            "Педали": r"\bпедал(?:ь|и)\b",
        }
        if category in terms:
            value = re.sub(terms[category], " ", value, flags=re.I)
        value = re.sub(r"\b(\w+)\s+\1\b", r"\1", value, flags=re.I)
        value = re.sub(r"\s+", " ", value).strip(" -,.[]")
        return value[:200] or "Модель"

    def unique_category_slug(self, parent, title):
        base = slugify(title)[:44] or "other"
        slug, n = base, 2
        while Category.objects.filter(slug=slug).exclude(parent=parent, title=title).exists():
            slug, n = f"{base[:40]}-{n}", n + 1
        return slug

    def download_image(self, variant, brand, url, title):
        if not url or (variant.images.exists() and brand.image):
            return
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            # A removed CDN image must not abort publication of every product
            # that follows it in the Taobao export.
            self.stderr.write(f"Фото пропущено ({url}): {exc}")
            return
        name = Path(urlparse(url).path).name or f"{variant.pk}.jpg"
        if not variant.images.exists():
            image = Image(variant=variant, alt=title, sort=0)
            image.image.save(name, ContentFile(response.content), save=True)
        if not brand.image:
            brand.image.save(f"{brand.slug}-{name}", ContentFile(response.content), save=True)
