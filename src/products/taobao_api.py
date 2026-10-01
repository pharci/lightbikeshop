import json
import secrets
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import TaobaoImportItem


def _decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


@csrf_exempt
@require_POST
def import_taobao_products(request):
    expected = getattr(settings, "TAOBAO_IMPORT_TOKEN", "")
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        return JsonResponse({"error": "unauthorized"}, status=401)
    try:
        items = json.loads(request.body)["items"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return JsonResponse({"error": "invalid_json"}, status=400)
    if not isinstance(items, list) or not 1 <= len(items) <= 500:
        return JsonResponse({"error": "items must contain 1..500 products"}, status=400)

    created = updated = 0
    with transaction.atomic():
        for item in items:
            store = str(item.get("store", "")).strip()
            external_id = str(item.get("external_id", "")).strip()
            title = str(item.get("title", "")).strip()
            if not store or not external_id or not title:
                continue
            _, was_created = TaobaoImportItem.objects.update_or_create(
                source_key=f"{store}:{external_id}",
                defaults={
                    "store": store, "external_id": external_id, "title_original": title,
                    "title_ru": str(item.get("title_ru", "")).strip(),
                    "description_ru": str(item.get("description_ru", "")).strip(),
                    "category_name": str(item.get("category", "")).strip(),
                    "brand_name": str(item.get("brand", "")).strip(),
                    "variant_name": str(item.get("variant", "")).strip(),
                    "price_cny": _decimal(item.get("price_cny")),
                    "price_rub": _decimal(item.get("price_rub")),
                    "available": bool(item.get("available", False)),
                    "image_url": str(item.get("image_url", "")).strip(),
                    "product_url": str(item.get("url", "")).strip(), "raw": item,
                },
            )
            created += int(was_created)
            updated += int(not was_created)
    return JsonResponse({"ok": True, "created": created, "updated": updated})
