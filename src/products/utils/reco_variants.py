# products/reco_variants.py
from math import log1p
from collections import defaultdict
from django.db.models import Q
from products.models import Variant, AttributeValue, RelatedVariant, CopurchaseVariantStat

W_MAN, W_COP, W_CNT = 3.0, 2.0, 1.0

def _price_closeness(a: float, b: float) -> float:
    if not a or not b: return 0.0
    r = float(min(a, b) / max(a, b))
    return 0.2 * r  # 0..0.2

def _attr_signature(variant_ids: list[int]) -> dict[int, set[str]]:
    sig = defaultdict(set)
    qs = (AttributeValue.objects
          .select_related("attribute","variant__product__category")
          .filter(variant_id__in=variant_ids))
    for av in qs:
        a = av.attribute
        if a.value_type == "text":
            val = (av.value_text or "").strip().lower()
        elif a.value_type == "number":
            val = str(av.value_number).rstrip("0").rstrip(".")
        else:
            val = "1" if av.value_bool else "0"
        sig[av.variant_id].add(f"{a.slug}={val}")
    return sig

def _content_similarity(a: Variant, b: Variant, sig_map: dict[int,set[str]]) -> float:
    s = 0.0
    if a.product.category_id == b.product.category_id: s += 0.6
    if a.product.brand_id and a.product.brand_id == b.product.brand_id: s += 0.2
    s += _price_closeness(float(a.price or 0), float(b.price or 0))
    sig_a = sig_map.get(a.id, set()); sig_b = sig_map.get(b.id, set())
    if sig_a and sig_b:
        j = len(sig_a & sig_b) / max(1, len(sig_a | sig_b))
        s += 0.2 * min(j, 1.0)  # добавка за пересечение атрибутов
    return min(s, 1.0)

def recommend_variants_with(variant: Variant, limit: int = 12) -> list[Variant]:
    vid = variant.id
    cand = defaultdict(lambda: {"man":0.0,"cop":0.0,"cnt":0.0,"pinned":False})

    # ручные/авто связи
    for rl in (RelatedVariant.objects
               .select_related("to_variant","to_variant__product")
               .filter(from_variant=variant, is_active=True)
               .order_by("-pinned","-weight","position","id")):
        if rl.to_variant.inventory <= 0: 
            continue
        cand[rl.to_variant_id]["man"] = max(cand[rl.to_variant_id]["man"], float(rl.weight))
        cand[rl.to_variant_id]["pinned"] |= rl.pinned

    # ко-покупки
    for p in (CopurchaseVariantStat.objects
              .filter(Q(variant_min_id=vid)|Q(variant_max_id=vid))
              .values("variant_min_id","variant_max_id","count")):
        other = p["variant_max_id"] if p["variant_min_id"] == vid else p["variant_min_id"]
        cand[other]["cop"] = max(cand[other]["cop"], float(p["count"]))

    # контентная похожесть в пуле соседей
    pool = (Variant.objects
            .filter(is_active=True)
            .select_related("product")
            .filter(product__category_id=variant.product.category_id)
            .exclude(id=vid))
    sig_map = _attr_signature(list(pool.values_list("id", flat=True)) + [vid])
    for b in pool:
        if b.inventory > 0:
            cand[b.id]["cnt"] = max(cand[b.id]["cnt"], _content_similarity(variant, b, sig_map))

    # скоринг и правила
    scored = []
    for other_id, s in cand.items():
        if other_id == vid: 
            continue
        b = Variant.objects.filter(is_active=True).select_related("product").only(
            "id","price","inventory","product__brand_id","product__category_id"
        ).get(id=other_id)
        if b.inventory <= 0: 
            continue
        score = (W_MAN*s["man"]) + (W_COP*log1p(s["cop"])) + (W_CNT*s["cnt"])
        if variant.product.category_id == b.product.category_id: score += 0.2
        if variant.product.brand_id and variant.product.brand_id == b.product.brand_id: score += 0.1
        scored.append((s["pinned"], score, float(b.price or 0), b))

    scored.sort(key=lambda t: (not t[0], -t[1], t[2]))

    # diversity по бренду
    cap_per_brand = 3
    used = defaultdict(int)
    out = []
    for _, _, _, b in scored:
        key = b.product.brand_id or 0
        if used[key] >= cap_per_brand: 
            continue
        used[key] += 1
        out.append(b)
        if len(out) >= limit: 
            break
    return out
