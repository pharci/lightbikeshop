from django.db.models import Prefetch
from django.shortcuts import render

from .models import Category, Brand

from .list_utils import *
from .detail_utils import *

def list(request, category_path=None, brand=None):
    params = parse_params(request)
    cat, br = get_cat_brand_by_path(category_path, brand)

    qs = base_qs()
    qs = apply_scope(qs, cat, br, params)
    by_slug = attr_slug_map(cat)
    qs = apply_attr_filters(qs, params, by_slug)
    qs = order_qs(qs, params.sort)
    page_obj = paginate_qs(qs, params.page)

    fb = faceting_base_qs(cat, br, params)
    price_rng = price_range_facet(fb)
    brands = brand_facet(fb)
    attrs = attr_facets(cat, fb)

    ctx = {
        "variants": page_obj.object_list,
        "page_obj": page_obj,
        "q": params.q,
        "cat": cat,
        "brand": br,
        "notfound": page_obj.paginator.count == 0,
        "sort": params.sort,
        "price_range": price_rng,
        "brand_facet": brands,
        "attr_facets": attrs,
        "selected": selected_dict(request, params),
        "qs": qs_without_page(request),
    }
    return render(request, "products/list.html", ctx)


def detail(request, category_path, slug, variant_id):
    variant = get_variant_or_404(variant_id)
    siblings = get_sibling_variants_qs(variant.product_id)

    attrs, attr_ids = variant_attributes(variant)
    variants_data, values_by_attr, first_by_attr_val = build_variants_index(siblings, attr_ids)
    current_values = current_values_map(variant, attr_ids)
    rows = build_rows(attrs, attr_ids, values_by_attr, first_by_attr_val, variants_data, current_values)

    return render(request, "products/detail.html", {
        "variant": variant,
        "base": variant.product,
        "rows": rows,
    })


def catalog(request):
    roots = (
        Category.objects.filter(parent__isnull=True)
        .order_by("name")
        .prefetch_related(
            Prefetch("children", queryset=Category.objects.order_by("name"))
        )
    )
    
    brands = Brand.objects.all()
    
    return render(request, 'products/catalog.html', {
        'brands': brands,
        'roots': roots,
        })