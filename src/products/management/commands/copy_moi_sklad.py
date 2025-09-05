# products/management/commands/import_moysklad_full.py
import time
import requests
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.core.files.base import ContentFile
from decimal import Decimal
from django.conf import settings

from products.models import (
    Category, Brand, Product, Variant, Attribute, CategoryAttribute, AttributeValue, Image
)


from products.MS.load_products import (
    _get, save_variant_images, save_variant_attributes, _pick_prices, _walk_pages,
    _ensure_category_chain, HEADERS, PAGE_LIMIT
)


class Command(BaseCommand):
    help = "Полная синхронизация с МойСклад: продукты, модификации, остатки. PK = внешние ID (UUID строки)."

    def add_arguments(self, parser):
        parser.add_argument("--no-stock", action="store_true", help="Не обновлять остатки (только каталог)")

    def handle(self, *args, **opts):
        self.stdout.write(self.style.NOTICE("1) Импорт товаров (product)..."))
        self._import_products()

        self.stdout.write(self.style.NOTICE("2) Импорт модификаций (variant)..."))
        self._import_variants()

        self.stdout.write(self.style.SUCCESS("Готово."))

    # ---------- PRODUCTS ----------
    def _import_products(self):
        url = f"{settings.MOYSKLAD_BASE}/entity/product"
        params = {
            "limit": PAGE_LIMIT,
            "offset": 0,
            "expand": "productFolder,images",
            "order": "updated"
        }

        created, updated = 0, 0
        for page in _walk_pages(url, params):
            rows = page.get("rows", [])
            for p in rows:
                ms_id = (p.get("id")).strip()     # внешний ID => PK
                if not ms_id:
                    continue

                name = (p.get("name") or "").strip()
                desc = p.get("description") or ""
                path_name = p.get("pathName") or ""
                category = _ensure_category_chain(path_name)

                w = p.get("weight")
                weight = int(round(w)) if isinstance(w, (int, float)) and w > 0 else None

                product, is_created = Product.objects.update_or_create(
                    id=ms_id,
                    defaults={
                        "base_name": name,
                        "description": desc,
                        "category": category,
                        "brand": None,
                        "weight": weight,
                    }
                )
                created += int(is_created)
                updated += int(not is_created)

        self.stdout.write(self.style.SUCCESS(f"Products: created={created}, updated={updated}"))

    # ---------- VARIANTS ----------
    def _import_variants(self):
        url = f"{settings.MOYSKLAD_BASE}/entity/variant"
        params = {
            "limit": PAGE_LIMIT,
            "offset": 0,
            "expand": "characteristics,product,images",
            "order": "updated",
        }

        created, updated = 0, 0
        for page in _walk_pages(url, params):
            for v in page.get("rows", []):
                v_id = (v.get("id")).strip()          # внешний ID варианта => PK
                if not v_id:
                    continue

                p_data = v.get("product") or {}
                p_id = (p_data.get("id")).strip()     # внешний ID продукта
                if not p_id:
                    continue

                # продукт должен существовать по PK=external_id
                try:
                    product = Product.objects.only("id").get(id=p_id)
                except Product.DoesNotExist:
                    continue

                price, old_price = _pick_prices(v.get("salePrices") or p_data.get("salePrices"))

                defaults = {
                    "product": product,
                }
                if price is not None:
                    defaults["price"] = price
                if old_price is not None and hasattr(Variant, "old_price"):
                    defaults["old_price"] = old_price

                variant, is_created = Variant.objects.update_or_create(id=v_id, defaults=defaults)
                created += int(is_created)
                updated += int(not is_created)

                # При необходимости включи картинки/атрибуты:
                save_variant_images(variant, v.get("images"), HEADERS)
                save_variant_attributes(variant.product, variant, v.get("characteristics"), is_variant=True)

        self.stdout.write(self.style.SUCCESS(f"Variants: created={created}, updated={updated}"))
