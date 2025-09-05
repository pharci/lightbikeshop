from itertools import combinations
from django.db.models import F
from django.db import transaction
from products.models import CopurchaseVariantStat

def bump_copurchases_variants(variant_ids: list[int]) -> None:
    ids = sorted(set(v for v in variant_ids if v))
    if len(ids) < 2: return
    with transaction.atomic():
        for a, b in combinations(ids, 2):
            obj, created = CopurchaseVariantStat.objects.get_or_create(
                variant_min_id=a, variant_max_id=b, defaults={"count": 1}
            )
            if not created:
                CopurchaseVariantStat.objects.filter(pk=obj.pk).update(count=F("count")+1)