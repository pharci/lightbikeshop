# views/products.py
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from django.core.paginator import Paginator
from django.db.models import Q, Case, When, IntegerField, Exists, OuterRef, Value, Prefetch, Min, Max, QuerySet
from django.db.models.functions import Cast
from django.db.models import CharField

from django.shortcuts import get_object_or_404
from django.http import Http404

from products.models import (
    Variant, AttributeValue, CategoryAttribute,
    Category, Brand, Attribute
)

SORT_MAP = {
    'pop':  ['-has_stock', '-id'],
    'price_asc':  ['-has_stock', 'price', '-id'],
    'price_desc': ['-has_stock', '-price', '-id'],
    'newest':     ['-has_stock', '-created', '-id'],
}


def apply_text_search(qs, q: str):
    tokens = [t for t in (q or "").split() if t]
    if not tokens:
        return qs

    def attr_exists(tok: str):
        sub = (AttributeValue.objects
               .filter(variant_id=OuterRef('pk'))
               .annotate(vn_str=Cast('value_number', output_field=CharField()))
               .filter(Q(value_text__icontains=tok) | Q(vn_str__icontains=tok)))
        return Exists(sub)

    for tok in tokens:
        qs = qs.filter(
            Q(product__base_name__icontains=tok) |
            Q(product__brand__title__icontains=tok) |
            Q(product__category__second_name__icontains=tok) |
            Q(product__category__name__icontains=tok) |
            attr_exists(tok) |
            Q(slug__icontains=tok) |
            Q(wb_article__icontains=tok) |
            Q(ozon_article__icontains=tok)
        )

    rank = (
        Case(
            When(product__base_name__istartswith=tokens[0], then=Value(4)),
            default=Value(0), output_field=IntegerField()
        )
        + Case(
            When(product__brand__title__istartswith=tokens[0], then=Value(3)),
            default=Value(0), output_field=IntegerField()
        )
        + Case(
            When(product__base_name__icontains=" ".join(tokens), then=Value(2)),
            default=Value(0), output_field=IntegerField()
        )
        + Case(
            When(product__brand__title__icontains=" ".join(tokens), then=Value(1)),
            default=Value(0), output_field=IntegerField()
        )
    )

    return qs.annotate(search_rank=rank).order_by('-search_rank')

def _parse_decimal(s: Optional[str]):
    try:
        if s is None or str(s).strip() == "":
            return None
        return round(float(str(s).replace(",", ".")), 6)
    except Exception:
        return None

@dataclass(frozen=True)
class FilterParams:
    q: str
    page: int
    sort: str
    price_min: Optional[float]
    price_max: Optional[float]
    in_stock: bool
    brand_slugs: List[str]
    attr_params: Dict[str, str]

def parse_params(request) -> FilterParams:
    q = (request.GET.get("q") or "").strip()
    page = int(request.GET.get("page", 1))
    sort = request.GET.get("sort") or "pop"
    price_min = _parse_decimal(request.GET.get("price_min"))
    price_max = _parse_decimal(request.GET.get("price_max"))
    in_stock = request.GET.get("in_stock") == "1"
    brands_raw = (request.GET.get("brands") or "").strip()
    brand_slugs = [s for s in brands_raw.split(",") if s] if brands_raw else []
    attr_params = {k: v for k, v in request.GET.items() if k.startswith("a_")}
    return FilterParams(q, page, sort, price_min, price_max, in_stock, brand_slugs, attr_params)

def get_cat_brand_by_path(category_path: Optional[str], brand_slug: Optional[str]) -> Tuple[Optional[Category], Optional[Brand]]:
    cat = None
    if category_path:
        parts = category_path.strip("/").split("/")
        parent = None
        for slug in parts:
            try:
                parent = Category.objects.get(parent=parent, slug=slug)
            except Category.DoesNotExist:
                raise Http404("Категория не найдена")
        cat = parent
    br = get_object_or_404(Brand, slug=brand_slug) if brand_slug else None
    return cat, br

def base_qs() -> QuerySet:
    return (
        Variant.objects
        .filter(is_active=True)
        .select_related("product", "product__brand", "product__category")
        .prefetch_related(
            "images",
            Prefetch(
                "attribute_values",
                queryset=AttributeValue.objects.select_related("attribute")
            ),
            Prefetch(
                "product__category__category_attributes",
                queryset=CategoryAttribute.objects.select_related("attribute").order_by("sort_order", "id")
            ),
        )
        .annotate(
            has_stock=Case(
                When(Q(inventory__gt=0), then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    )

def apply_scope(qs: QuerySet, cat: Optional[Category], br: Optional[Brand], params: FilterParams) -> QuerySet:
    cat_ids = effective_category_ids(cat)
    if cat_ids:
        qs = qs.filter(product__category_id__in=cat_ids)
    if br:
        qs = qs.filter(product__brand=br)
    if params.q:
        qs = apply_text_search(qs, params.q)
    if params.in_stock:
        qs = qs.filter(has_stock=1)
    if params.price_min is not None:
        qs = qs.filter(price__gte=params.price_min)
    if params.price_max is not None:
        qs = qs.filter(price__lte=params.price_max)
    if params.brand_slugs and not br:
        qs = qs.filter(product__brand__slug__in=params.brand_slugs)
    return qs

def attr_slug_map(cat: Optional[Category]) -> Dict[str, Attribute]:
    if cat:
        cas = list(cat.category_attributes.select_related("attribute").filter(is_filterable=True))
        return {ca.attribute.slug: ca.attribute for ca in cas}
    attrs = Attribute.objects.all()
    return {a.slug: a for a in attrs}

def apply_attr_filters(qs: QuerySet, params: FilterParams, by_slug: Dict[str, Attribute]) -> QuerySet:
    for key, val in params.attr_params.items():
        if not key.startswith("a_"):
            continue
        body = key[2:]
        if body.endswith("_min") or body.endswith("_max"):
            slug = body[:-4]
            a = by_slug.get(slug)
            if not a or a.value_type != Attribute.NUMBER:
                continue
            num = _parse_decimal(val)
            if num is None:
                continue
            if body.endswith("_min"):
                qs = qs.filter(attribute_values__attribute__slug=slug,
                               attribute_values__value_number__gte=num)
            else:
                qs = qs.filter(attribute_values__attribute__slug=slug,
                               attribute_values__value_number__lte=num)
        else:
            slug = body
            a = by_slug.get(slug)
            if not a:
                continue
            if a.value_type == Attribute.TEXT:
                values = [s for s in val.split(",") if s]
                if values:
                    qs = qs.filter(attribute_values__attribute__slug=slug,
                                   attribute_values__value_text__in=values)
            elif a.value_type == Attribute.BOOL:
                if val in ("0", "1"):
                    qs = qs.filter(attribute_values__attribute__slug=slug,
                                   attribute_values__value_bool=(val == "1"))
            elif a.value_type == Attribute.NUMBER:
                num = _parse_decimal(val)
                if num is not None:
                    qs = qs.filter(attribute_values__attribute__slug=slug,
                                   attribute_values__value_number=num)
    return qs

def order_qs(qs: QuerySet, sort: str) -> QuerySet:
    order_by = SORT_MAP.get(sort, SORT_MAP["pop"])
    return qs.order_by(*order_by).distinct()

def paginate_qs(qs: QuerySet, page: int, per_page: int = 24):
    return Paginator(qs, per_page).get_page(page)

# ---------- фасеты ----------

def faceting_base_qs(cat, br, params):
    qs = Variant.objects.select_related("product", "product__brand", "product__category")\
        .annotate(has_stock=Case(When(Q(inventory__gt=0), then=Value(1)),
                                 default=Value(0), output_field=IntegerField()))
    # вместо простого cat-фильтра:
    cat_ids = effective_category_ids(cat)
    if cat_ids:
        qs = qs.filter(product__category_id__in=cat_ids)
    return apply_scope(qs, None, br, params)  # cat уже учли

def price_range_facet(qs: QuerySet) -> Dict[str, Optional[float]]:
    return qs.aggregate(min=Min("price"), max=Max("price"))

def brand_facet(qs: QuerySet) -> List[Dict[str, str]]:
    return list(
        qs.values("product__brand__slug", "product__brand__title")
          .exclude(product__brand__slug__isnull=True)
          .distinct()
          .order_by("product__brand__title")
    )

def attr_facets(cat: Optional[Category], base_for_facets: QuerySet) -> List[dict]:
    if not cat:
        return []
    items = []
    for ca in cat.category_attributes.select_related("attribute").filter(is_filterable=True):
        a = ca.attribute
        item = {"attribute": a, "values": None, "range": None}
        if a.value_type == Attribute.TEXT:
            vals = (
                AttributeValue.objects
                .filter(attribute=a, variant__in=base_for_facets)
                .exclude(value_text="")
                .values_list("value_text", flat=True)
                .distinct().order_by("value_text")[:200]
            )
            item["values"] = list(vals)
        elif a.value_type == Attribute.BOOL:
            item["values"] = [{"label": "Да", "value": "1"}, {"label": "Нет", "value": "0"}]
        else:
            rng = (
                AttributeValue.objects
                .filter(attribute=a, variant__in=base_for_facets)
                .aggregate(min=Min("value_number"), max=Max("value_number"))
            )
            item["range"] = rng
        items.append(item)
    return items

def selected_dict(request, params: FilterParams) -> dict:
    return {
        "q": params.q,
        "sort": params.sort,
        "in_stock": params.in_stock,
        "price_min": request.GET.get("price_min") or "",
        "price_max": request.GET.get("price_max") or "",
        "brands": params.brand_slugs,
        "attrs": params.attr_params,
    }

def qs_without_page(request) -> str:
    qs_params = request.GET.copy()
    qs_params.pop("page", None)
    return qs_params.urlencode()


def effective_category_ids(cat, include_self=True):
    if not cat:
        return None
    ids = [cat.id] if include_self else []
    frontier = [cat.id]
    while frontier:
        children = list(
            Category.objects.filter(parent_id__in=frontier).values_list("id", flat=True)
        )
        if not children:
            break
        ids.extend(children)
        frontier = children
    return ids