from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from products.catalog_enrichment import apply_characteristics, extract_characteristics, taobao_item_id
from products.models import AttributeValue, Product, TaobaoImportItem


class Command(BaseCommand):
    help = "Объединяет SKU одной карточки Taobao и создаёт характеристики товаров"

    def handle(self, *args, **options):
        merged_products = 0
        groups = defaultdict(list)
        imports = list(TaobaoImportItem.objects.select_related("product", "variant"))
        for item in imports:
            parent_id = taobao_item_id(item.external_id)
            if parent_id and item.product_id and item.variant_id:
                groups[(item.store, parent_id)].append(item)

        with transaction.atomic():
            for items in groups.values():
                if len(items) < 2:
                    continue
                canonical = items[0].product
                for item in items:
                    if item.product_id != canonical.id:
                        old_product = item.product
                        item.variant.product = canonical
                        item.variant.save()
                        item.product = canonical
                        item.save(update_fields=["product"])
                        if not old_product.variants.exists():
                            old_product.delete()
                            merged_products += 1

        enriched = 0
        for product in Product.objects.select_related("category", "brand").prefetch_related("variants__taobao_imports"):
            variants = list(product.variants.all())
            parsed = []
            for variant in variants:
                source = variant.taobao_imports.order_by("-updated_at").first()
                parts = []
                if source:
                    parts += [source.variant_name, source.description_ru, source.title_original, source.title_ru]
                parts += [product.base_name, product.description]
                attrs = {
                    "Тип товара": product.category.title_singular or product.category.title,
                    "Единица продажи": "Пара" if variant.sales_unit == variant.SalesUnit.PAIR else "Штука",
                    **extract_characteristics(*parts),
                }
                parsed.append((variant, attrs))
            changing = {
                name for name in {key for _, attrs in parsed for key in attrs}
                if len({attrs.get(name) for _, attrs in parsed if attrs.get(name)}) > 1
            }
            AttributeValue.objects.filter(
                product=product,
                attribute__name__in=changing,
            ).delete()
            for variant, attrs in parsed:
                if attrs:
                    apply_characteristics(product, variant, attrs, variant_names=changing)
                    enriched += 1

        self.stdout.write(self.style.SUCCESS(
            f"Объединено карточек: {merged_products}; обработано вариантов: {enriched}"
        ))
