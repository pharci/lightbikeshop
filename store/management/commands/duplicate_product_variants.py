from django.core.management.base import BaseCommand
from store.models import Product, ProductVariant, AttributeVariant, ProductImage
from django.db import transaction
import random

class Command(BaseCommand):
    help = 'Duplicates all products and their variants to increase the number of items for pagination testing'

    def handle(self, *args, **options):
        products = Product.objects.all()
        count = 0
        with transaction.atomic():
            for product in products:
                new_product = Product(
                    category=product.category,
                    brand=product.brand,
                    name=product.name + " Copy",
                    slug=product.slug + "-copy" + str(random.randint(1, 99999)),
                    description=product.description,
                    meta_description=product.meta_description,
                    meta_keywords=product.meta_keywords
                )
                new_product.save()

                # Дублирование вариантов продукта
                for variant in product.variants.all():
                    new_variant = ProductVariant(
                        product=new_product,
                        sku=variant.sku + "-copy" + str(random.randint(1, 99999)),
                        price=variant.price,
                        recommendation=variant.recommendation,
                        new=variant.new
                    )
                    new_variant.save()

                    # Дублирование атрибутов вариантов
                    for attr_variant in variant.attribute_variants.all():
                        new_attr_variant = AttributeVariant(
                            variant=new_variant,
                            attribute=attr_variant.attribute,
                            value=attr_variant.value,
                            is_main=attr_variant.is_main,
                            is_filter=attr_variant.is_filter
                        )
                        new_attr_variant.save()

                    # Дублирование изображений, если необходимо
                    for image in variant.images.all():
                        new_image = ProductImage(
                            variant=new_variant,
                            image=image.image,
                            is_main=image.is_main
                        )
                        new_image.save()

                count += 1
        self.stdout.write(self.style.SUCCESS(f'Successfully duplicated {count} products with variants'))