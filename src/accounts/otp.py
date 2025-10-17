# accounts/otp.py — единый источник ключей и HMAC для e-mail OTP
import os
import hmac
import hashlib
import secrets
from django.conf import settings
from typing import Tuple, Optional

ACTIVE_ID = 'otp_a'
PREV_ID = 'otp_b'

def _key_bytes(s: str) -> bytes:
    """Поддержка hex-строк и обычных строк."""
    try:
        return bytes.fromhex(s)
    except ValueError:
        return s.encode()

def secret_for_id(secret_id: str) -> bytes:
    v = os.getenv(f"OTP_KEY_{secret_id}", "")
    if not v:
        # Пустой ключ недопустим. Лучше fail-fast.
        raise RuntimeError(f"Нет ключа в окружении: OTP_KEY_{secret_id}")
    return _key_bytes(v)

def current_id() -> str:
    """ID текущего секрета для подписи новых кодов."""
    return ACTIVE_ID

def sign_with_id(code: str, secret_id: str) -> str:
    """HMAC-SHA256(code, key(secret_id)) → hex."""
    return hmac.new(secret_for_id(secret_id), code.encode(), hashlib.sha256).hexdigest()

def verify_with_id(code: str, stored_hmac: str, secret_id: str) -> bool:
    """Проверка с конкретным secret_id."""
    return hmac.compare_digest(stored_hmac, sign_with_id(code, secret_id))

def verify_with_rotation(code: str, stored_hmac: str) -> Tuple[bool, Optional[str]]:
    """
    Проверка c ротацией ключей.
    Возвращает (ok, used_secret_id) где used_secret_id ∈ {ACTIVE_ID, PREV_ID} или None.
    """
    if verify_with_id(code, stored_hmac, ACTIVE_ID):
        return True, ACTIVE_ID
    if PREV_ID and PREV_ID != ACTIVE_ID and verify_with_id(code, stored_hmac, PREV_ID):
        return True, PREV_ID
    return False, None

def gen_code(length: int = 6) -> str:
    """Генерация цифрового OTP без ведущих обрезаний: строго length цифр."""
    if length <= 0:
        raise ValueError("length must be > 0")
    # secrets.randbelow надёжнее для OTP
    upper = 10 ** length
    n = secrets.randbelow(upper)
    return f"{n:0{length}d}"  # нули слева сохраняются
