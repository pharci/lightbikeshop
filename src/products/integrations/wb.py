import requests
from django.conf import settings


def wb_get_nm_id(vendor_code: str) -> int | None:
    r = requests.post(
        f"{settings.WB_API_URL}/content/v2/get/cards/list",
        headers={
            "Authorization": settings.WB_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "settings": {
                "filter": {"textSearch": vendor_code, "withPhoto": -1}
            }
        },
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    cards = data.get("cards") or []
    return cards[0].get("nmID") if cards else None