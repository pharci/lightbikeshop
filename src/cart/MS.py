import uuid, datetime as dt
from decimal import Decimal
import requests
from django.conf import settings
from .money import as_kop
from requests.exceptions import HTTPError

BASE = settings.MOYSKLAD_BASE
HDRS = {
    "Authorization": f"Bearer {settings.MOYSKLAD_TOKEN}",
    "Accept-Encoding": "gzip",
    "User-Agent": "DjangoShop/1.0",
}

def _meta(entity: str, _id: str) -> dict:
    return {"meta": {
        "href": f"{BASE}/entity/{entity}/{_id}",
        "type": entity,
        "mediaType": "application/json"
    }}

def _get(url, params=None):
    r = requests.get(url, headers=HDRS, params=params, timeout=30)
    if r.status_code >= 400:
        try: print("MS GET ERROR:", r.text[:2000])
        except: pass
    r.raise_for_status()
    return r.json()

def _post(url, json):
    r = requests.post(url, headers=HDRS, json=json, timeout=60)
    if r.status_code >= 400:
        try: print("MS ERROR:", r.text[:2000])
        except: pass
    r.raise_for_status()
    return r.json()

# ---------- Контрагент ----------

def _find_or_create_counterparty(name: str, phone: str, email: str) -> dict:
    q = (phone or email or name or "").strip()
    if q:
        data = _get(f"{BASE}/entity/counterparty", params={"search": q, "limit": 1})
        rows = data.get("rows") or []
        if rows:
            return {"meta": rows[0]["meta"]}

    default_id = getattr(settings, "MOYSKLAD_DEFAULT_COUNTERPARTY_ID", None)
    if default_id:
        return _meta("counterparty", default_id)

    payload = {
        "name": (name or phone or email or "Покупатель").strip()[:255],
        "phone": (phone or "").strip(),
        "email": (email or "").strip(),
    }
    created = _post(f"{BASE}/entity/counterparty", payload)
    return {"meta": created["meta"]}

# ---------- Ассортимент ----------

def _resolve_assortment_meta(variant) -> dict:
    """
    У тебя Variant.id == GUID из МС.
    1) если есть variant.id -> это variant
    2) иначе берём product.id как product
    """
    vid = getattr(variant, "id", None)
    if vid:
        return _meta("variant", str(vid))

    prod = getattr(variant, "product", None)
    pid = getattr(prod, "id", None)
    if pid:
        return _meta("product", str(pid))

    raise RuntimeError(f"Не найден ассортимент для варианта id={getattr(variant, 'id', None)}")

# ---------- Документ заказа ----------

def build_ms_order_payload(order) -> dict:
    agent_meta = _find_or_create_counterparty(order.user_name, order.contact_phone, order.email)

    positions = []
    for item in order.items.select_related("variant", "variant__product"):
        positions.append({
            "quantity": int(item.quantity),
            "price": as_kop(item.price),
            "assortment": _resolve_assortment_meta(item.variant),
        })

    desc = []
    if order.pvz_code:
        desc.append(f"ПВЗ: {order.pvz_code}")
    else:
        desc.append("Самовывоз")
    if order.order_notes:
        desc.append(order.order_notes)
    description = "\n\n".join(desc)

    addr_raw = (order.pvz_address or "").strip()
    shipmentAddress = addr_raw[:255] if addr_raw else ""

    shipmentAddressFull = {
        "countryIsoCode": "RU",
        "city": (order.city or "").strip() or None,
        "street": addr_raw or None,
    }
    shipmentAddressFull = {k: v for k, v in shipmentAddressFull.items() if v}

    return {
        "name": f"LBS-{order.order_id}",
        "moment": order.date_ordered.strftime("%Y-%m-%d %H:%M:%S"),
        "agent": agent_meta,
        "organization": _meta("organization", settings.MOYSKLAD_ORGANIZATION_ID),
        "store": _meta("store", settings.MOYSKLAD_STORE_ID),
        "salesChannel": _meta("saleschannel", settings.MOYSKLAD_SALESCHANNEL_ID),
        "positions": positions,
        "vatIncluded": True,
        "applicable": True,
        "shipmentAddress": shipmentAddress,
        "shipmentAddressFull": shipmentAddressFull or None,
        "description": description,
        "externalCode": order.order_id,  # ключ идемпотентности вместо syncId
    }

def create_customer_order(order) -> dict | None:
    payload = build_ms_order_payload(order)
    try:
        return _post(f"{BASE}/entity/customerorder", payload)
    except HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status == 409:
            found = _get(f"{BASE}/entity/customerorder?filter=externalCode={order.order_id}")
            rows = (found or {}).get("rows") or []
            return rows[0] if rows else None
        if status in (500, 502, 503, 504):
            raise
        return None
    except (TimeoutError, ConnectionError):
        raise


# смена статуса заказа
def set_ms_order_state_by_uuid(order_uuid: str | uuid.UUID, state_uuid: str | uuid.UUID) -> dict:
    """Установить статус customerorder по UUID документа и UUID статуса."""
    ou = str(order_uuid)
    su = str(state_uuid)
    body = {
        "state": {
            "meta": {
                "href": f"{BASE}/entity/customerorder/metadata/states/{su}",
                "type": "state",
                "mediaType": "application/json",
            }
        },
        "reserve": True
    }
    r = requests.put(f"{BASE}/entity/customerorder/{ou}", headers=HDRS, json=body, timeout=30)
    if r.status_code >= 400:
        try: print("MS ERROR:", r.text[:2000])
        except: pass
    r.raise_for_status()
    return r.json()