from __future__ import annotations

import json
import logging
import time

import requests
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

log = logging.getLogger(__name__)

_token_cache = {"access": None, "exp": 0}


def _get_token() -> str:
    now = time.time()
    if _token_cache["access"] and _token_cache["exp"] - 60 > now:
        return _token_cache["access"]

    url = f"{settings.CDEK_BASE}/v2/oauth/token"
    r = requests.post(
        url,
        data={"grant_type": "client_credentials"},
        auth=(settings.CDEK_ID, settings.CDEK_SECRET),
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        timeout=20,
    )
    if r.status_code >= 400:
        try:
            body = r.json()
        except Exception:
            body = r.text
        log.error("CDEK OAuth failed %s: %s", r.status_code, body)
        r.raise_for_status()

    data = r.json()
    _token_cache["access"] = data["access_token"]
    _token_cache["exp"] = now + int(data.get("expires_in", 3600))
    return _token_cache["access"]


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {_get_token()}"}


def _passthrough(resp: requests.Response) -> HttpResponse:
    return HttpResponse(
        resp.content,
        status=resp.status_code,
        content_type=resp.headers.get("Content-Type", "application/json"),
    )


@csrf_exempt
def cdek_service(request: HttpRequest):
    """
    Универсальный прокси для CDEK Widget v3:
      action=offices    → GET  /v2/deliverypoints
      action=calculate  → POST /v2/calculator/tarifflist
      action=cities     → GET  /v2/location/cities
    """
    action = (request.GET.get("action") or "").lower()
    try:
        if action == "offices":
            url = f"{settings.CDEK_BASE}/v2/deliverypoints"
            r = requests.get(url, headers=_auth_headers(), params=request.GET, timeout=20)
            return _passthrough(r)

        elif action == "calculate":
            url = f"{settings.CDEK_BASE}/v2/calculator/tarifflist"
            try:
                payload = json.loads(request.body or b"{}")
            except Exception:
                payload = {}
            r = requests.post(
                url,
                headers={**_auth_headers(), "Content-Type": "application/json"},
                json=payload,
                timeout=25,
            )
            return _passthrough(r)

        elif action == "cities":
            url = f"{settings.CDEK_BASE}/v2/location/cities"
            q = request.GET.get("city") or request.GET.get("q") or request.GET.get("term") or ""
            params = {
                "city": q,
                "size": request.GET.get("size", 50),
                "country_codes": request.GET.get("country_codes", "RU"),
            }
            r = requests.get(url, headers=_auth_headers(), params=params, timeout=20)
            return _passthrough(r)

        else:
            return JsonResponse({"error": "unknown action"}, status=400)

    except requests.RequestException as e:
        # 502 для наглядности проблем апстрима
        return HttpResponse(f"Upstream error: {e}", status=502, content_type="text/plain")
