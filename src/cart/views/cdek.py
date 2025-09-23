import re, hashlib, requests
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from cart.models import PickupPoint
from cart.views.cart import get_cart
from decimal import Decimal as D

CDEK_AUTH_URL = "https://api.cdek.ru/v2/oauth/token"
CDEK_CITY_URL = "https://api.cdek.ru/v2/location/cities"
CDEK_PVZ_URL  = "https://api.cdek.ru/v2/deliverypoints"
CDEK_CALC_URL = "https://api.cdek.ru/v2/calculator/tariff"

def _safe_cache_key(prefix: str, *parts) -> str:
    raw = ":".join(str(p).strip() for p in parts if p is not None)
    key = f"{prefix}:{raw}"
    # оставить только допустимые символы
    key = re.sub(r"[^A-Za-z0-9:._-]", "_", key)
    # страховка по длине (лимит ~250 байт у memcached)
    if len(key) > 230:
        digest = hashlib.md5(key.encode("utf-8")).hexdigest()
        key = f"{prefix}:{digest}"
    return key

def _get_token():
    key = _safe_cache_key("cdek_token")
    cached = cache.get(key)
    if cached:
        return cached["access_token"]
    resp = requests.post(
        CDEK_AUTH_URL,
        data={"grant_type": "client_credentials"},
        auth=(settings.CDEK_ID, settings.CDEK_SECRET),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    # запас по времени
    cache.set(key, data, data.get("expires_in", 3600) - 120)
    return data["access_token"]

def _auth_headers():
    return {"Authorization": f"Bearer {_get_token()}"}

def get_city_code(city: str):
    key = _safe_cache_key("cdek_city", city)
    code = cache.get(key)
    if code:
        return code
    r = requests.get(
        CDEK_CITY_URL,
        params={"city": city, "country_codes": "RU"},
        headers=_auth_headers(),
        timeout=20,
    )
    r.raise_for_status()
    items = r.json()
    if not items:
        return None
    code = items[0]["code"]
    cache.set(key, code, 24 * 3600)
    return code

def get_pvz(city: str):
    code = get_city_code(city)
    if not code:
        return []
    r = requests.get(
        CDEK_PVZ_URL,
        params={"city_code": code, "type": "PVZ", "is_handout": "true", "active": "true"},
        headers=_auth_headers(),
        timeout=20,
    )
    r.raise_for_status()
    out = []
    for p in r.json():
        loc = p.get("location") or {}
        if "latitude" not in loc or "longitude" not in loc:
            continue
        out.append({
            "id": p.get("code"),
            "name": p.get("name") or "СДЭК ПВЗ",
            "address": loc.get("address") or "",
            "lat": loc.get("latitude"),
            "lon": loc.get("longitude"),
            "city_code": loc.get("city_code"),
            "provider": "cdek",
        })
    return out


def get_pvz_by_code(code: str) -> dict | None:
    if not code:
        return None
    cache_key = _safe_cache_key("cdek_pvz", code)
    cached = cache.get(cache_key)
    if cached:
        return cached
    r = requests.get(
        CDEK_PVZ_URL,
        params={"code": code},
        headers=_auth_headers(),
        timeout=20,
    )
    r.raise_for_status()
    items = r.json()
    pvz = items[0] if items else None
    if pvz:
        cache.set(cache_key, pvz, 6 * 3600)
    return pvz

def calc_price(from_code: int, to_code: int, weight: int, tariff_code: int = 136) -> dict:
    """136 = склад-склад (ПВЗ→ПВЗ). Для курьера возьми 137 (склад-дверь)."""
    body = {
        "from_location": {"code": from_code},
        "to_location": {"code": to_code},
        "packages": [{"weight": weight}],
        "tariff_code": tariff_code,
    }
    r = requests.post(CDEK_CALC_URL, headers={**_auth_headers(), "Content-Type": "application/json"}, json=body, timeout=20)
    r.raise_for_status()
    return r.json()


def calc_cdek_pvz_price(cart, pvz_code: str, to_city_code: str | None = None) -> tuple[D, dict]:
    """Возвращает (цена, meta). Не кидает исключений."""
    price = D("0.00")
    meta = {}
    try:
        w = int(cart.get_total_weight() or 0)
        if not to_city_code:
            pvz = get_pvz_by_code(pvz_code) or {}
            loc = pvz.get("location") or {}
            to_city_code = loc.get("city_code")
        if not to_city_code:
            return price, {"error": "CITY_CODE_NOT_FOUND"}
        data = calc_price(
            from_code=int(settings.CDEK_SENDER_CODE),
            to_code=int(to_city_code),
            weight=w,
            tariff_code=136,  # склад-склад
        )
        
        price = D(str(data.get("total_sum") or "0")) + D(100)
        meta = {
            "tariff_code": 136,
            "period_min": data.get("period_min"),
            "period_max": data.get("period_max"),
            "to_city_code": to_city_code,
        }
        return price, meta
    except Exception as e:
        return D("0.00"), {"error": "UNEXPECTED", "detail": str(e)}





@require_GET
def get_cities(request):
    """Вернёт список всех городов СДЭК"""
    cache_key = "cdek_all_cities"
    data = cache.get(cache_key)
    if not data:
        r = requests.get(CDEK_CITY_URL, headers=_auth_headers(), timeout=30)
        r.raise_for_status()
        items = r.json()
        # оставляем только нужные поля
        data = [{"code": i["code"], "city": i["city"], "region": i.get("region")} for i in items]
        cache.set(cache_key, data, 24*3600)
    return JsonResponse(data, safe=False)

@require_GET
def api_shop_pvz(request):
    city = request.GET.get("city", "").strip()
    qs = PickupPoint.objects.filter(is_active=True)
    if city:
        qs = qs.filter(city__iexact=city)
    data = [{"id": f"{p.code}", "name": p.title, "address": p.address,
             "lat": float(p.lat), "lon": float(p.lon), "provider": "Самовывоз"} for p in qs]
    return JsonResponse(data, safe=False)

@require_GET
def api_cdek_pvz(request):
    city = request.GET.get("city", "").strip()
    data = get_pvz(city) if city else []
    return JsonResponse(data, safe=False)


@require_POST
def api_cdek_price(request):
    pvz_code = (request.POST.get("pvz_code") or "").strip()
    to_city_code = request.POST.get("to_city_code")
    cart = get_cart(request)

    price, meta = calc_cdek_pvz_price(cart, pvz_code, to_city_code)
    if meta.get("error") == "CITY_CODE_NOT_FOUND":
        return JsonResponse({"ok": False, "error": "CITY_CODE_NOT_FOUND"}, status=400)
    return JsonResponse({
        "ok": True,
        "price": float(price),
        "currency": "RUB",
        "period_min": meta.get("period_min"),
        "period_max": meta.get("period_max"),
        "tariff_code": meta.get("tariff_code", 136),
    })