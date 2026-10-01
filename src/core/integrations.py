from django.conf import settings
from django.core.cache import cache


def integration_value(key, default=""):
    """Return an admin-managed secret, falling back to environment settings."""
    cache_key = f"integration-key:{key}"
    try:
        cached = cache.get(cache_key)
    except Exception:
        cached = None
    if cached is not None:
        return cached
    value = ""
    try:
        from core.models import IntegrationKey
        record = IntegrationKey.objects.filter(key=key).only("encrypted_value").first()
        value = record.get_value() if record else ""
    except Exception:
        # The database may be unavailable or migrations may still be running.
        value = ""
    value = value or getattr(settings, key, default) or default
    try:
        cache.set(cache_key, value, 60)
    except Exception:
        pass
    return value
