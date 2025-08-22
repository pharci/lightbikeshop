import time
import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from products.models import Variant

# ==== настройки ====
MOYSKLAD_TOKEN = "d0fbdeffca46b98d07bc35054d8d82e845eb2007"
BASE_URL = "https://api.moysklad.ru/api/remap/1.2"
HEADERS = {
    "Authorization": f"Bearer {MOYSKLAD_TOKEN}",
    "Accept-Encoding": "gzip",
    "User-Agent": "DjangoSync/1.0",
}
SLEEP_BETWEEN_REQUESTS = 0.1
# ===================

def _get(url, params=None):
    r = requests.get(url, headers=HEADERS, params=params, timeout=60)
    if r.status_code >= 400:
        print("ERROR:", r.text[:500])
    r.raise_for_status()
    return r.json()

def iter_stock_rows(params: dict):
    """Итератор по строкам отчёта stock/all/current (dict|list)."""
    url = f"{BASE_URL}/report/stock/all/current"

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

class Command(BaseCommand):
    help = "Обновить наличие: пришедшим из МойСклад — фактическое значение, остальным — 0."

    def handle(self, *args, **opts):
        params = {"groupBy": "variant"}

        report_ids = set()   # external_id, встреченные в отчёте
        to_update = []       # Variant с изменённым inventory

        # 1) собрать остатков и подготовить апдейты для совпавших
        for row in iter_stock_rows(params):
            meta = (row.get("assortment") or {}).get("meta") or {}
            href = meta.get("href") or ""
            vid = row.get("assortmentId") or (href.rstrip("/").split("/")[-1] if href else None)
            if not vid:
                continue

            report_ids.add(vid)
            qty = int(row.get("stock", 0) or 0)

            v = Variant.objects.filter(external_id=vid).only("id", "inventory").first()
            if not v:
                continue
            if v.inventory != qty:
                v.inventory = qty
                to_update.append(v)

        # 2) применить изменения к совпавшим
        updated_matched = 0
        if to_update:
            with transaction.atomic():
                Variant.objects.bulk_update(to_update, ["inventory"])
            updated_matched = len(to_update)

        # 3) всем, кто есть в БД, но НЕ пришёл в отчёте — выставить 0
        zero_qs = (
            Variant.objects
            .filter(external_id__isnull=False)
            .exclude(external_id__in=report_ids)
        )
        zeroed = zero_qs.update(inventory=0)

        total_db = Variant.objects.filter(external_id__isnull=False).count()
        matched = Variant.objects.filter(external_id__in=report_ids).count()

        self.stdout.write(self.style.SUCCESS(
            f"Всего в БД: {total_db}; сопоставлено: {matched}; обновлено: {updated_matched}; обнулено: {zeroed}"
        ))
