# accounts/security.py
import time
import secrets
from functools import wraps
from typing import Iterable, Optional

from django.shortcuts import redirect


# ===== ВСПОМОГАТЕЛЬНОЕ =====

def now_epoch() -> int:
    return int(time.time())


def set_action_guard(request, action: str, ttl_minutes: int = 30) -> str:
    """
    Выдать одноразовый nonce для шага (login/registration/recovery) и сохранить в сессии.
    """
    nonce = secrets.token_urlsafe(16)
    request.session["action"] = action
    request.session["action_nonce"] = nonce
    request.session["action_exp"] = now_epoch() + ttl_minutes * 60
    request.session.modified = True
    return nonce


def clear_action_guard(request) -> None:
    for k in ("action", "action_nonce", "action_exp"):
        if k in request.session:
            del request.session[k]


def require_action(allowed: Optional[Iterable[str]] = None):
    """
    Декоратор: проверка, что в сессии есть валидный шаг (action) и nonce не истёк.
    allowed — допустимые значения action (например: {"login","registration","recovery"}).
    """
    allowed_set = set(allowed) if allowed else None

    def deco(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            action = request.session.get("action")
            nonce = request.session.get("action_nonce")
            exp   = request.session.get("action_exp")

            if not action or not nonce or not exp:
                return redirect("accounts:login")

            if allowed_set and action not in allowed_set:
                return redirect("accounts:login")

            if now_epoch() > int(exp):
                clear_action_guard(request)
                return redirect("accounts:login")

            return view_func(request, *args, **kwargs)
        return wrapper
    return deco


# ===== ПРОСТОЙ RATE-LIMIT НА СЕССИИ =====

def hit_rate_limit(request, key: str, cooldown_sec: int) -> bool:
    """
    Возвращает True, если ещё рано (слишком часто). Иначе помечает текущий таймштамп и возвращает False.
    Работает на сессии — подходит для базовой защиты от спама кодами.
    """
    bucket = request.session.get("rl", {})
    last_ts = int(bucket.get(key, 0))
    now = now_epoch()
    if now - last_ts < cooldown_sec:
        return True
    bucket[key] = now
    request.session["rl"] = bucket
    request.session.modified = True
    return False
