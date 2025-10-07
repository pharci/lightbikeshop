import os, time, requests
from typing import Iterator, Dict, Any
from django.db import transaction
from products.models import Variant
from django.conf import settings

HEADERS = {
    "Authorization": f"Bearer {settings.MOYSKLAD_TOKEN_ADMIN}",
    "Accept-Encoding": "gzip",
    "User-Agent": "DjangoSync/1.0",
}
SLEEP_BETWEEN_REQUESTS = 0.1

def _get(url: str, params=None) -> dict:
    r = requests.get(url, headers=HEADERS, params=params, timeout=60)
    r.raise_for_status()
    return r.json()

def _iter_stock_rows(params: Dict[str, Any]) -> Iterator[dict]:
    url = f"{settings.MOYSKLAD_BASE}/report/stock/all/current"

    def yield_rows(data):
        if isinstance(data, dict):
            for r in data.get("rows", []):
                yield r
        elif isinstance(data, list):
            for r in data:
                yield r

    data = _get(url, params=params)
    for r in yield_rows(data):
        yield r
    while isinstance(data, dict):
        next_href = (data.get("meta") or {}).get("nextHref")
        if not next_href:
            break
        data = _get(next_href)
        for r in yield_rows(data):
            yield r
        time.sleep(SLEEP_BETWEEN_REQUESTS)

def sync_inventory() -> dict:
    params = {"groupBy": "variant"}
    report_ids, to_update = set(), []

    for row in _iter_stock_rows(params):
        meta = (row.get("assortment") or {}).get("meta") or {}
        href = meta.get("href") or ""
        vid = row.get("assortmentId") or (href.rstrip("/").split("/")[-1] if href else None)
        if not vid:
            continue

        qty = int(row.get("stock", 0) or 0)
        if qty < 0:  # skip negative values
            qty = 0

        report_ids.add(vid)
        v = Variant.objects.filter(id=vid).only("id", "inventory").first()
        if v and v.inventory != qty:
            v.inventory = qty
            to_update.append(v)

    updated = 0
    if to_update:
        with transaction.atomic():
            Variant.objects.bulk_update(to_update, ["inventory"])
        updated = len(to_update)

    zeroed = (
        Variant.objects
        .filter(id__isnull=False)
        .exclude(id__in=report_ids)
        .update(inventory=0)
    )
    total_db = Variant.objects.filter(id__isnull=False).count()
    matched = Variant.objects.filter(id__in=report_ids).count()
    return {"total": total_db, "matched": matched, "updated": updated, "zeroed": zeroed}
