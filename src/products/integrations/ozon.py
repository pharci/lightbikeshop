import requests
from django.conf import settings

def get_sku_by_offer_id(offer_id: str) -> int | None:
    headers = {
        "Client-Id": str(settings.OZON_CLIENT_ID),
        "Api-Key": settings.OZON_API_KEY,
        "Content-Type": "application/json",
    }
    body = {"offer_id": [offer_id]}
    resp = requests.post(
        f"{settings.OZON_API_URL}/v3/product/info/list",
        headers=headers,
        json=body,
        timeout=10
    )
    resp.raise_for_status()
    items = resp.json().get("items") or []
    return items[0].get("sku") if items else None