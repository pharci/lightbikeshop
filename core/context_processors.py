# core/context_processors.py
from django.urls import reverse, NoReverseMatch
from django.apps import apps
from products.models import Category, Brand, Variant

def _rev(name, fallback="/"):
    try:
        return reverse(name)
    except NoReverseMatch:
        return fallback

def _get(model_label):
    try:
        return apps.get_model(model_label)
    except Exception:
        return None

BREADCRUMB_RULES = [
    ("prefix", "/catalog/",  "Каталог",  ("catalog", "list")),
    ("prefix", "/brands/",   "Бренды",   ("brands", "list")),
    ("exact",  "/cart/",     "Корзина",  None),
    ("exact",  "/checkout/", "Оформление заказа", None),
    ("exact",  "/faq/",      "FAQ",      None),
    ("exact",  "/login/",    "Вход",      None),
    ("exact",  "/register/", "Регистрация", None),
    ("exact",  "/profile/",  "Профиль",      None),
    ("route",  ("catalog","search"), "Поиск", None),
    ("route",  ("products","catalog_search"), "Поиск", None),
]

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
                items.append((title, None))
                return True
    return False

def _title_from_segment(seg: str) -> str:
    return seg.replace("-", " ").capitalize()

def breadcrumbs(request):
    path = (request.path or "/").rstrip("/") + "/"
    rm = getattr(request, "resolver_match", None)
    kw = rm.kwargs if rm else {}

    if path == "/":
        return {"breadcrumbs": []}

    items = [("Главная", _rev("home", "/"))]

    if _apply_rules(items, path, rm):
        return {"breadcrumbs": items}


    brand_slug = kw.get("brand") or kw.get("brand_slug")
    if brand_slug:
        try:
            b = Brand.objects.only("title", "slug").get(slug=brand_slug)
            items.append((b.title, None))
            return {"breadcrumbs": items}
        except Brand.DoesNotExist:
            pass

    # путь категории
    cat_path = kw.get("category_path")
    if cat_path:
        parts = [p for p in cat_path.strip("/").split("/") if p]
        for i, seg in enumerate(parts):
            cat = Category.objects.get(slug=seg)
            title = cat.name
            items.append((title, None))

    # товар
    variant_id = kw.get("variant_id")
    if variant_id:
        if items:
            items[-1] = (items[-1][0], None)
            v = Variant.objects.get(pk=variant_id)
        items.append((v.display_name(), None))
        return {"breadcrumbs": items}

    # если это страница категории по пути
    if cat_path:
        items[-1] = (items[-1][0], None)
        return {"breadcrumbs": items}

    return {"breadcrumbs": items}