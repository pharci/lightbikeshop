# products/management/commands/import_moysklad_full.py
import time
import requests
from urllib.parse import urlparse, parse_qs
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.core.files.base import ContentFile
from decimal import Decimal

from products.models import (
    Category, Brand, Product, Variant, Attribute, CategoryAttribute, AttributeValue, Image
)

# ====== НАСТРОЙКИ ======
MOYSKLAD_TOKEN = "f537ad8ab222e376902fe98641f3ec8de30c1747"  # <-- АНДРЕЙ
BASE_URL = "https://api.moysklad.ru/api/remap/1.2"
HEADERS = {
    "Authorization": f"Bearer {MOYSKLAD_TOKEN}",
    "Accept-Encoding": "gzip",
    "User-Agent": "DjangoSync/1.0",
}
PAGE_LIMIT = 100           # expand работает только при limit<=100
SLEEP_BETWEEN_REQUESTS = 0.1  # чуть-чуть бережём API
# =======================

ATTR_TYPE_MAP = {
    "string": Attribute.TEXT,
    "text": Attribute.TEXT,
    "long": Attribute.NUMBER,
    "double": Attribute.NUMBER,
    "boolean": Attribute.BOOL,
}

def _get(url, params=None):
    r = requests.get(url, headers=HEADERS, params=params, timeout=60)
    if r.status_code >= 400:
        # Показать текст ошибки от МС — очень полезно
        try:
            print("ERROR BODY:", r.text[:1000])
        except Exception:
            pass
    r.raise_for_status()
    return r.json()


def _walk_pages(first_url, params=None):
    """Итератор по всем страницам: идём по meta.nextHref, пока есть."""
    data = _get(first_url, params=params)
    yield data
    while True:
        m = data.get("meta") or {}
        next_href = m.get("nextHref")
        if not next_href:
            break
        # nextHref уже полный URL со всеми параметрами
        data = _get(next_href)
        yield data
        time.sleep(SLEEP_BETWEEN_REQUESTS)


def _ensure_category_chain(path_name: str, leaf_name: str) -> Category:
    """
    В МС у папки есть pathName (например 'BMX/Bottom bracket'),
    причём для самой папки pathName — это ПУТЬ ДО РОДИТЕЛЯ (без собственного имени).
    В товаре:
      pathName = 'BMX/Bottom bracket'
      productFolder.name = 'Bottom bracket'
    Нам надо собрать цепочку категорий: 'BMX' -> 'Bottom bracket'
    и вернуть конечную категорию 'Bottom bracket'.
    """
    segments = [seg.strip() for seg in (path_name or "").split("/") if seg.strip()]
    if not segments or (segments and segments[-1].lower() != leaf_name.strip().lower()):
        # На всякий — добиваем лист, если его нет в конце
        segments.append(leaf_name.strip())

    parent = None
    cat = None
    for seg in segments:
        cat, _ = Category.objects.get_or_create(
            name=seg,
            defaults={"slug": slugify(seg)}
        )
        # Если у тебя у Category есть parent — тут можно проставлять/проверять parent
        # Пример (раскомментируй и добавь поле parent в модель):
        # if cat.parent_id != (parent.id if parent else None):
        #     cat.parent = parent
        #     cat.save(update_fields=["parent"])
        parent = cat
    return cat


def _price_from_sale_prices(sale_prices):
    """Возвращаем Decimal цены из первого типа цены. МС присылает число; берём как есть."""
    if not sale_prices:
        return Decimal("0")
    value = sale_prices[0].get("value") or 0
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")

def _rub_from_value(v):
    try:
        return (Decimal(str(v or 0)) / Decimal("100")).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")

def _pick_prices(sale_prices):
    """
    Возвращает (price, old_price) из массива salePrices по именам типов цен.
    """
    price = old_price = None
    for p in sale_prices or []:
        name = (p.get("priceType", {}) or {}).get("name", "").strip().lower()
        val = _rub_from_value(p.get("value"))
        if name == "цена продажи":
            price = val
        elif name == "старая цена":
            old_price = val
    return price, old_price

def ensure_attribute(name: str, value_type: str) -> Attribute:
    """
    Возвращает атрибут по имени без учёта регистра.
    Если нет — создаёт с уникальным slug.
    """
    nm = (name or "").strip()
    vt = ATTR_TYPE_MAP.get(value_type, Attribute.TEXT)

    # 1) ищем по имени (без регистра)
    attr = Attribute.objects.filter(name__iexact=nm).first()
    if attr:
        if attr.value_type != vt:
            attr.value_type = vt
            attr.save(update_fields=["value_type"])
        return attr

    # 2) slugify (кириллица → allow_unicode=True)
    slug = slugify(nm, allow_unicode=True) or "attr"

    # 3) если slug занят, добавляем суффикс, но игнорируем совпадение по имени (другой регистр)
    base_slug = slug
    i = 2
    while Attribute.objects.filter(slug=slug).exclude(name__iexact=nm).exists():
        slug = f"{base_slug}-{i}"
        i += 1

    # 4) создаём
    return Attribute.objects.create(name=nm, slug=slug, value_type=vt)

def save_variant_attributes(product, variant, ms_attributes: list, is_variant: bool = False):
    """
    Сохраняем атрибуты в AttributeValue и привязываем их к категории.
    """
    if not ms_attributes:
        return

    for a in ms_attributes:
        name = (a.get("name") or "").strip()
        if not name:
            continue

        # Для характеристик модификаций в МС типа нет — всегда TEXT
        atype = "string" if is_variant else a.get("type", "string")
        attr = ensure_attribute(name, atype)
        # Привязка атрибута к категории
        if product.category_id:
            ca, _ = CategoryAttribute.objects.get_or_create(
                category=product.category,
                attribute=attr,
                defaults={
                    "is_required": False,
                    "is_filterable": True,
                    "is_variant": is_variant
                }
            )
            if is_variant and not ca.is_variant:
                ca.is_variant = True
                ca.save(update_fields=["is_variant"])

        # Готовим значение
        pav_defaults = {"value_text": "", "value_number": None, "value_bool": None}
        if attr.value_type == Attribute.TEXT:
            pav_defaults["value_text"] = str(a.get("value") or "").strip()
        elif attr.value_type == Attribute.NUMBER:
            try:
                pav_defaults["value_number"] = Decimal(str(a.get("value")))
            except Exception:
                pav_defaults["value_number"] = None
        elif attr.value_type == Attribute.BOOL:
            pav_defaults["value_bool"] = bool(a.get("value"))

        pav, created = AttributeValue.objects.update_or_create(
            variant=variant,
            attribute=attr,
            defaults=pav_defaults
        )

def save_variant_images(variant, images_obj: dict, headers: dict):
    """
    Сохраняем фото для варианта (Image).
    """
    rows = (images_obj or {}).get("rows") or []
    if not rows:
        return

    for sort_index, img in enumerate(rows):
        download_href = img.get("meta", {}).get("downloadHref")
        if not download_href:
            continue
        r = requests.get(download_href, headers=headers, timeout=30)
        if r.status_code == 200:
            filename = f"{variant.sku or variant.external_id}_{sort_index}.jpg"
            Image.objects.create(
                variant=variant,
                image=ContentFile(r.content, name=filename),
                sort=sort_index
            )

class Command(BaseCommand):
    help = "Полная синхронизация с МойСклад: продукты, модификации, остатки"

    def add_arguments(self, parser):
        parser.add_argument("--no-stock", action="store_true", help="Не обновлять остатки (только каталог)")

    def handle(self, *args, **opts):
        self.stdout.write(self.style.NOTICE("1) Импорт товаров (product)..."))
        self._import_products()

        self.stdout.write(self.style.NOTICE("2) Импорт модификаций (variant)..."))
        self._import_variants()

        # if not opts["no_stock"]:
        #     self.stdout.write(self.style.NOTICE("3) Обновление остатков по модификациям..."))
        #     self._update_stock()

        self.stdout.write(self.style.SUCCESS("Готово."))

    # ---------- PRODUCTS ----------
    def _import_products(self):
        url = f"{BASE_URL}/entity/product"
        params = {
            "limit": PAGE_LIMIT,
            "offset": 0,
            "expand": "productFolder,images",
            "order": "updated"  # не обязательно
        }

        created, updated = 0, 0
        for page in _walk_pages(url, params):
            rows = page.get("rows", [])
            for p in rows:
                pid = p.get("id")
                name = (p.get("name") or "").strip()
                desc = p.get("description") or ""
                code = (p.get("code") or "").strip()

                # Категория
                pf = p.get("productFolder")
                path_name = p.get("pathName") or ""
                category = None
                if pf and pf.get("name"):
                    category = _ensure_category_chain(path_name, pf["name"])

                # Бренд (если используешь в МС — подцепи из атрибутов/названия)
                brand = None
                # Пример: brand_name = (p.get("brand", {}) or {}).get("name")

                # Цена
                price = _price_from_sale_prices(p.get("salePrices"))

                product, is_created = Product.objects.update_or_create(
                    external_id=pid,
                    defaults={
                        "base_name": name,
                        "description": desc,
                        "category": category,
                        "brand": brand,
                        "slug": "",  # если автогенерация в save(), можно оставить пустым
                    }
                )
                created += int(is_created)
                updated += int(not is_created)

                # Картинки (если нужны: p["images"]["rows"] -> meta.downloadHref)
                # В примере у тебя пусто; показать скачивание:
                # for img in (p.get("images", {}).get("rows") or []):
                #     dl = img.get("meta", {}).get("downloadHref")
                #     if dl:
                #         self._download_and_attach_image(product, dl)

        self.stdout.write(self.style.SUCCESS(f"Products: created={created}, updated={updated}"))

    # def _download_and_attach_image(self, product, download_href: str):
    #     r = requests.get(download_href, headers=HEADERS, timeout=60)
    #     r.raise_for_status()
    #     # product.image.save(...)

    # ---------- VARIANTS ----------
    def _import_variants(self):
        url = f"{BASE_URL}/entity/variant"
        params = {
            "limit": PAGE_LIMIT,
            "offset": 0,
            "expand": "characteristics,product,images",  # <-- добавили product, чтобы взять цены у родителя
            "order": "updated",
        }

        created, updated = 0, 0
        for page in _walk_pages(url, params):
            rows = page.get("rows", [])
            for v in rows:
                vid = v.get("id")
                code = (v.get("code") or "").strip()  # артикул варианта

                # Определяем родительский товар
                product_meta = (v.get("product") or {}).get("meta") or {}
                href = product_meta.get("href") or ""
                parent_id = href.rstrip("/").split("/")[-1] if href else None
                product = Product.objects.filter(external_id=parent_id).first()
                if not product:
                    # Если вдруг модификация пришла раньше товара — пропускаем
                    continue

                # Достаём цены: сперва пробуем у варианта, затем у родителя
                v_sale_prices = v.get("salePrices")  # иногда у варианта может быть свой прайс
                p_sale_prices = (v.get("product") or {}).get("salePrices")
                price, old_price = _pick_prices(v_sale_prices or p_sale_prices)

                defaults = {
                    "product": product,
                    "sku": code,
                }
                if price is not None:
                    defaults["price"] = price
                if old_price is not None and hasattr(Variant, "old_price"):
                    defaults["old_price"] = old_price

                variant, is_created = Variant.objects.update_or_create(
                    external_id=vid,
                    defaults=defaults,
                )
                created += int(is_created)
                updated += int(not is_created)

                # Фото варианта (если в expand=images при запросе entity/variant)
                save_variant_images(variant, v.get("images"), HEADERS)
                # Атрибуты варианта (характеристики)
                save_variant_attributes(product, variant, v.get("characteristics"), is_variant=True)

        self.stdout.write(self.style.SUCCESS(f"Variants: created={created}, updated={updated}"))

    # ---------- STOCK ----------
    def _update_stock(self):
        # Остатки по модификациям
        url = f"{BASE_URL}/report/stock/all/current"
        params = {
            "groupBy": "variant",
            # "changedSince": "2025-08-01 00:00:00",  # включай позже для инкрементальных апдейтов
        }

        updated = 0
        for page in _walk_pages(url, params):
            rows = page.get("rows", [])
            for row in rows:
                # В отчёте бывают два варианта: либо 'assortment' с meta.href, либо прямо 'assortmentId'
                meta = (row.get("assortment") or {}).get("meta") or {}
                href = meta.get("href") or ""
                variant_id = row.get("assortmentId") or (href.rstrip("/").split("/")[-1] if href else None)
                if not variant_id:
                    continue

                qty = row.get("stock", 0)  # свободный остаток: см. stockType, если нужно freeStock по складам

                variant = Variant.objects.filter(external_id=variant_id).first()
                if not variant:
                    continue

                variant.inventory = int(qty) if qty is not None else 0
                # Статус доступности (если поле есть)
                if hasattr(variant, "availability_status"):
                    variant.availability_status = "in_stock" if (variant.inventory or 0) > 0 else "out_of_stock"
                variant.save(update_fields=["inventory"] + (["availability_status"] if hasattr(variant, "availability_status") else []))
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Stock updated for {updated} variants"))
