import time
import requests
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.core.files.base import ContentFile
from decimal import Decimal
from django.conf import settings
from django.db import transaction

from products.models import (
    Category, Brand, Product, Variant, Attribute, CategoryAttribute, AttributeValue, Image
)

from products.integrations.ozon import get_sku_by_offer_id
from products.integrations.wb import wb_get_nm_id

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

def get(url, params=None):
    r = requests.get(url, headers=HEADERS, params=params, timeout=60)
    if r.status_code >= 400:
        try: print("ERROR BODY:", r.text[:1000])
        except Exception: pass
    r.raise_for_status()
    return r.json()

def walk_pages(first_url, params=None):
    data = get(first_url, params=params)
    yield data
    while True:
        m = data.get("meta") or {}
        next_href = m.get("nextHref")
        if not next_href:
            break
        data = get(next_href)
        yield data
        time.sleep(SLEEP_BETWEEN_REQUESTS)

def ensure_category_chain(path: str) -> Category | None:
    segments = [s.strip() for s in (path or "").split("/") if s.strip()]
    if not segments:
        return None
    parent = None
    leaf = None
    for seg in segments:
        cat = Category.objects.filter(title__iexact=seg, parent=parent).first()
        if cat: 
            parent = leaf = cat 
            continue

        base_slug = slugify(seg)
        slug = base_slug or "cat"
        i = 2
        while Category.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{i}"
            i += 1

        leaf = Category.objects.create(title=seg, slug=slug, parent=parent)
        parent = leaf
    return leaf

def rub_from_value(v):
    try: return (Decimal(str(v or 0)) / Decimal("100")).quantize(Decimal("0.01"))
    except Exception: return Decimal("0.00")

def pick_prices(sale_prices):
    price = old_price = None
    for p in sale_prices or []:
        name = (p.get("priceType", {}) or {}).get("name", "").strip().lower()
        val = rub_from_value(p.get("value"))
        if name == "цена продажи": price = val
        elif name == "старая цена": old_price = val
    return price, old_price

def save_variant_images(variant, images_obj: dict, headers: dict):
    rows = (images_obj or {}).get("rows") or []

    with transaction.atomic():
        for img_obj in Image.objects.filter(variant=variant):
            if img_obj.image: img_obj.image.delete(save=False)
            img_obj.delete()

        if not rows: return

        for sort_index, img in enumerate(rows):
            download_href = img.get("meta", {}).get("downloadHref")
            if not download_href:
                continue
            r = requests.get(download_href, headers=headers, timeout=30)
            if r.ok and r.content:
                filename = f"{variant.id}_{sort_index}.jpg"
                Image.objects.create(
                    variant=variant,
                    image=ContentFile(r.content, name=filename),
                    sort=sort_index,
                )


def import_all_products():
    url = f"{settings.MOYSKLAD_BASE}/entity/product"
    params = {"limit": PAGE_LIMIT, "offset": 0, "expand": "productFolder,images", "order": "updated"}
    created = 0
    for page in walk_pages(url, params):
        rows = page.get("rows", [])
        for p in rows:
            ms_id = (p.get("id")).strip()     # внешний ID => PK
            if not ms_id: continue
            if Product.objects.filter(id=ms_id).exists(): continue

            name = (p.get("name") or "").strip()
            desc = p.get("description") or ""
            path_name = p.get("pathName") or ""
            category = ensure_category_chain(path_name)

            w = p.get("weight")
            weight = int(round(w)) if isinstance(w, (int, float)) and w > 0 else None

            Product.objects.create(id=ms_id, base_name=name, description=desc, category=category, brand=None, weight=weight)
            created += 1

    return f"Products: created={created}"


def import_all_variants():
    url=f"{settings.MOYSKLAD_BASE}/entity/variant"
    params={"limit":PAGE_LIMIT,"offset":0,"expand":"characteristics,product,images","order":"updated"}
    created=0
    for page in walk_pages(url,params):
        for v in page.get("rows",[]):
            v_id=(v.get("id") or "").strip()
            if not v_id or Variant.objects.filter(id=v_id).exists():continue
            p_id=((v.get("product") or {}).get("id") or "").strip()
            if not p_id:continue
            try:product=Product.objects.only("id").get(id=p_id)
            except Product.DoesNotExist:continue
            seller=(v.get("code") or v.get("externalCode") or "").strip() or None
            price,old=pick_prices(v.get("salePrices") or (v.get("product") or {}).get("salePrices"))
            variant=Variant.objects.create(
                id=v_id,product=product,seller_article=seller,
                ozon_article=(get_sku_by_offer_id(seller) if seller else None),
                wb_article=(wb_get_nm_id(seller) if seller else None),
                price=price,old_price=old
            )
            created+=1
            save_variant_images(variant,v.get("images"),HEADERS)
    return f"Variants: created={created}"