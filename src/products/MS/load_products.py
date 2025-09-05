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

# ====== НАСТРОЙКИ ======
HEADERS = {
    "Authorization": f"Bearer {settings.MOYSKLAD_TOKEN}",
    "Accept-Encoding": "gzip",
    "User-Agent": "DjangoSync/1.0",
}
PAGE_LIMIT = 100                 # expand работает только при limit<=100
SLEEP_BETWEEN_REQUESTS = 0.1     # чуть бережём API
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
        data = _get(next_href)
        yield data
        time.sleep(SLEEP_BETWEEN_REQUESTS)


def _ensure_category_chain(path_name: str) -> Category | None:
    """
    Строит дерево категорий по 'BMX/Rims/...' и возвращает лист.
    Учитывает parent. Глобально уникальный slug: если конфликт — добавляет суффикс -2, -3...
    """
    segments = [s.strip() for s in (path_name or "").split("/") if s.strip()]
    if not segments:
        return None

    parent = None
    leaf = None
    for seg in segments:
        # 1) пробуем найти по имени + parent (без учёта регистра)
        cat = Category.objects.filter(name__iexact=seg, parent=parent).first()
        if cat:
            parent = leaf = cat
            continue

        # 2) готовим уникальный slug среди всех категорий
        base_slug = slugify(seg)
        slug = base_slug or "cat"
        i = 2
        while Category.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{i}"
            i += 1

        # 3) создаём узел
        leaf = Category.objects.create(name=seg, slug=slug, parent=parent)
        parent = leaf

    return leaf


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

    attr = Attribute.objects.filter(name__iexact=nm).first()
    if attr:
        if attr.value_type != vt:
            attr.value_type = vt
            attr.save(update_fields=["value_type"])
        return attr

    slug = slugify(nm, allow_unicode=True) or "attr"
    base_slug = slug
    i = 2
    while Attribute.objects.filter(slug=slug).exclude(name__iexact=nm).exists():
        slug = f"{base_slug}-{i}"
        i += 1

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

        atype = "string" if is_variant else a.get("type", "string")
        attr = ensure_attribute(name, atype)

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

        AttributeValue.objects.update_or_create(
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
            filename = f"{variant.id}_{sort_index}.jpg"
            Image.objects.create(
                variant=variant,
                image=ContentFile(r.content, name=filename),
                sort=sort_index
            )