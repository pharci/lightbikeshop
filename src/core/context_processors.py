# core/context_processors.py
from django.urls import reverse, NoReverseMatch
from django.apps import apps
from products.models import Category, Brand
from .models import Page
from django.core.cache import cache
from django.utils.timezone import localtime

def _rev(name, fallback="/"):
    try:
        return reverse(name)
    except NoReverseMatch:
        return fallback

BREADCRUMB_RULES = [
    ("prefix", "/catalog/",  "Каталог",  ("catalog", "list")),
    ("prefix", "/brands/",   "Бренды",   ("brands", "list")),
    ("exact",  "/cart/",     "Корзина",  None),
    ("exact",  "/faq/",      "FAQ",      None),
    ("exact",  "/login/",    "Вход",      None),
    ("exact",  "/register/", "Регистрация", None),
    ("exact",  "/profile/",  "Профиль",      None),
    ("route",  ("cart","checkout"), "Оформление заказа", None),
    ("route",  ("catalog","search"), "Поиск", None),
]

def _parent_link(kind, key, route):
    if kind == "prefix" and route:
        ns, name = route
        return _rev(f"{ns}:{name}", key)
    return key

def _find_parent_for(url: str):
    parent = None
    best = -1
    for kind, key, title, route in BREADCRUMB_RULES:
        if kind in ("prefix", "exact") and url.startswith(key) and len(key) > best:
            parent = (kind, key, title, route)
            best = len(key)
    return parent

def _apply_rules(items, path, rm):
    for kind, key, title, route in BREADCRUMB_RULES:
        if kind == "prefix" and path.startswith(key):
            ns, name = route
            items.append((title, _rev(f"{ns}:{name}", key)))
            if path == key:
                items[-1] = (title, None)
                return True

        elif kind == "exact" and path == key:
            items.append((title, None))
            return True

        elif kind == "route" and rm:
            ns, name = key
            if rm.namespace == ns and rm.url_name == name:
                # URL текущего роута
                cur_url = _rev(f"{ns}:{name}", "")
                # найти родителя среди prefix/exact по этому URL
                parent = _find_parent_for(cur_url) if cur_url else None
                if parent:
                    pkind, pkey, ptitle, proute = parent
                    # если родитель не совпадает с самим URL, добавляем
                    if pkey != cur_url:
                        items.append((ptitle, _parent_link(pkind, pkey, proute)))
                items.append((title, None))
                return True
    return False

def breadcrumbs(request):
    path = (request.path or "/").rstrip("/") + "/"
    rm = getattr(request, "resolver_match", None)
    kw = rm.kwargs if rm else {}

    if path == "/":
        return {"breadcrumbs": []}

    items = [("Главная", _rev("home", "/"))]

    if _apply_rules(items, path, rm):
        return {"breadcrumbs": items}
    
    if path.startswith("/legal/"):
        slug = kw.get("slug")
        if not slug:
            # на случай прямого вызова без resolver_match
            parts = [p for p in path.strip("/").split("/") if p]
            slug = parts[1] if len(parts) > 1 else ""
        title = Page.objects.filter(slug=slug, is_published=True)\
                            .values_list("title", flat=True).first() or "Документ"
        items.append((title, None))
        return {"breadcrumbs": items}

    brand_slug = kw.get("brand") or kw.get("brand_slug")
    if brand_slug:
        try:
            b = Brand.objects.only("title", "slug").get(slug=brand_slug)
            items.append((b.title, None))
            return {"breadcrumbs": items}
        except Brand.DoesNotExist:
            pass

    cat_path = kw.get("category_path")
    if cat_path:
        parts = [p for p in cat_path.strip("/").split("/") if p]
        for i, seg in enumerate(parts):
            cat = Category.objects.get(slug=seg)
            items.append((cat, cat.get_absolute_url()))
        return {"breadcrumbs": items}

    return {"breadcrumbs": items}

def footer_pages(request):
    cols = {i: list(Page.objects.filter(is_published=True, column=i)) for i in (1,2,3,4)}
    return {"footer_cols": cols}