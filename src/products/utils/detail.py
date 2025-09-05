from typing import Dict, List, Tuple
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch

from products.models import (
    Variant, Image, AttributeValue, Attribute
)

# ---------- selectors ----------

def get_variant_or_404(slug) -> Variant:
    return get_object_or_404(
        Variant.objects
        .select_related("product", "product__brand", "product__category")
        .prefetch_related(
            Prefetch("attribute_values",
                     queryset=AttributeValue.objects.select_related("attribute")),
            Prefetch("images",
                     queryset=Image.objects.order_by("sort", "id")),
        ),
        slug=slug,
    )

def get_sibling_variants_qs(product_id):
    return (
        Variant.objects.filter(product_id=product_id)
        .select_related("product", "product__brand", "product__category")
        .prefetch_related(
            Prefetch("attribute_values",
                     queryset=AttributeValue.objects.select_related("attribute")),
            Prefetch("images",
                     queryset=Image.objects.order_by("sort", "id")),
        )
        .order_by("id")
    )

# ---------- formatting ----------

def fmt_value(pav: AttributeValue) -> str:
    a = pav.attribute
    if a.value_type == Attribute.TEXT:
        return pav.value_text
    if a.value_type == Attribute.NUMBER:
        return str(pav.value_number).rstrip("0").rstrip(".")
    return "Да" if pav.value_bool else "Нет"

# ---------- domain ----------

def variant_attributes(variant: Variant) -> Tuple[List[Attribute], List[int]]:
    cas = list(variant.product.variant_attributes)
    attrs = [ca.attribute for ca in cas]
    return attrs, [a.id for a in attrs]

def build_variants_index(variants_qs, attr_ids: List[int]):
    """
    Возвращает:
      variants_data: [{obj, attrs{attr_id->val}}]
      values_by_attr: {attr_id: [values]}
      first_by_attr_val: {attr_id: {value: variant}}
    """
    variants_data = []
    values_by_attr = {aid: [] for aid in attr_ids}
    first_by_attr_val = {aid: {} for aid in attr_ids}

    for v in variants_qs:
        vals = {
            p.attribute_id: fmt_value(p)
            for p in v.attribute_values.all() if p.attribute_id in attr_ids
        }
        variants_data.append({"obj": v, "attrs": vals})
        for aid, val in vals.items():
            if val not in values_by_attr[aid]:
                values_by_attr[aid].append(val)
            first_by_attr_val[aid].setdefault(val, v)

    return variants_data, values_by_attr, first_by_attr_val

def current_values_map(variant: Variant, attr_ids: List[int]) -> Dict[int, str]:
    pavs = {p.attribute_id: p for p in variant.attribute_values.all()}
    out = {}
    for aid in attr_ids:
        pav = pavs.get(aid)
        if pav:
            out[aid] = fmt_value(pav)
    return out

def find_variant_for(variants_data, selection: Dict[int, str]):
    for item in variants_data:
        attrs = item["attrs"]
        if all(attrs.get(aid) == val for aid, val in selection.items()):
            return item["obj"]
    return None

def number_aware_sort_key(s: str):
    from decimal import Decimal, InvalidOperation
    try:
        return (0, Decimal(s))
    except (InvalidOperation, TypeError):
        return (1, str(s))

def build_rows(attrs: List[Attribute],
               attr_ids: List[int],
               values_by_attr: Dict[int, List[str]],
               first_by_attr_val: Dict[int, Dict[str, Variant]],
               variants_data,
               current_values: Dict[int, str]):
    rows = []
    for a in attrs:
        aid = a.id
        items = []
        for val in sorted(values_by_attr.get(aid, []), key=number_aware_sort_key):
            desired = dict(current_values); desired[aid] = val
            match = find_variant_for(variants_data, desired)
            if match:
                items.append({
                    "text": val,
                    "url": match.get_absolute_url(),
                    "active": current_values.get(aid) == val,
                    "disabled": False,
                })
            else:
                fb = first_by_attr_val[aid].get(val)
                items.append({
                    "text": val,
                    "url": fb.get_absolute_url() if fb else "#",
                    "active": False,
                    "disabled": True,
                })
        rows.append({"label": a.name, "items": items})
    return rows