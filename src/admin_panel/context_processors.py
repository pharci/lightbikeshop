from django.core.cache import cache
from django.utils.timezone import localtime

def dashboard(request):
    last = cache.get("inv:last")
    return {
        "inv_last": localtime(last) if last else None,
        "inv_stats": cache.get("inv:stats") or {},
    }