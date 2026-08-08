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
    try:
        cached = cache.get(key)
    except Exception:
        cached = None
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
    try:
        cache.set(key, data, data.get("expires_in", 3600) - 120)
    except Exception:
        pass
    return data["access_token"]

def _auth_headers():
    return {"Authorization": f"Bearer {_get_token()}"}

def get_pvz_by_city_code(city_code: int):
    out = []
    page = 0
    while True:
        r = requests.get(
            CDEK_PVZ_URL,
            params={
                "city_code": city_code,
                "type": "PVZ",
                "is_handout": "true",
                "active": "true",
                "size": 1000,
                "page": page,
            },
            headers=_auth_headers(),
            timeout=20,
        )
        r.raise_for_status()

        items = r.json() or []
        if not items:
            break

        for p in items:
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

        if len(items) < 1000:
            break
        page += 1

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
        # Bind the quote to the selected CDEK pickup point, rather than a city
        # code controlled by the browser.
        pvz = get_pvz_by_code(pvz_code) or {}
        loc = pvz.get("location") or {}
        pvz_city_code = loc.get("city_code")
        if not pvz_city_code:
            return price, {"error": "CITY_CODE_NOT_FOUND"}
        try:
            to_code = int(pvz_city_code)
        except (TypeError, ValueError):
            return price, {"error": "INVALID_CITY_CODE"}
        try:
            if to_city_code and int(to_city_code) != to_code:
                return price, {"error": "PVZ_CITY_MISMATCH"}
        except (TypeError, ValueError):
            return price, {"error": "INVALID_CITY_CODE"}

        data = calc_price(
            from_code=int(settings.CDEK_SENDER_CODE),
            to_code=to_code,
            weight=w,
            tariff_code=136,  # склад-склад
        )

        if "total_sum" not in data:
            return price, {"error": "MALFORMED_RESPONSE"}
        price = D(str(data["total_sum"])) + D(100)
        meta = {
            "tariff_code": 136,
            "period_min": data.get("period_min"),
            "period_max": data.get("period_max"),
            "to_city_code": to_code,
        }
        return price, meta
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception("CDEK price calculation failed for pvz_code=%s city_code=%s", pvz_code, to_city_code)
        return D("0.00"), {"error": "UNEXPECTED", "detail": str(e)}





@require_GET
def get_cities(request):
    """Вернёт список всех городов СДЭК"""
    cache_key = "cdek_all_cities"
    data = None
    try:
        data = cache.get(cache_key)
    except Exception:
        # cache backend may be unavailable (redis down); proceed without cache
        data = None

    if not data:
        try:
            # Any exception raised here (auth/token failure, network, non-2xx) is
            # considered an external CDEK service failure — return 502.
            r = requests.get(CDEK_CITY_URL, headers=_auth_headers(), timeout=30)
            r.raise_for_status()
            items = r.json() or []
        except Exception as exc:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("CDEK external API unavailable when fetching cities: %s", exc)
            return JsonResponse({"error": "CDEK_UNAVAILABLE"}, status=502)

        # оставляем только нужные поля
        data = [{"code": i.get("code"), "city": i.get("city"), "region": i.get("region")} for i in items]
        try:
            cache.set(cache_key, data, 24*3600)
        except Exception:
            # cache set errors are non-fatal; treat as cache backend miss
            pass

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
    city_code = request.GET.get("city_code", "").strip()

    if not city_code:
        return JsonResponse([], safe=False)

    try:
        city_code = int(city_code)
    except ValueError:
        return JsonResponse([], safe=False)

    data = get_pvz_by_city_code(city_code)
    return JsonResponse(data, safe=False)


@require_POST
def api_cdek_price(request):
    pvz_code = (request.POST.get("pvz_code") or "").strip()
    to_city_code = request.POST.get("to_city_code")
    cart = get_cart(request)

    price, meta = calc_cdek_pvz_price(cart, pvz_code, to_city_code)

    if meta.get("error"):
        return JsonResponse({
            "ok": False,
            "error": meta["error"],
        }, status=400)

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
