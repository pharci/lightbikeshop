from django.db.models import Q
from .models import *

class ProductFilter:
    @staticmethod
    def get_brands(category_slug=None):
        query = Brand.objects.all()
        if category_slug:
            query = query.filter(products__category__slug=category_slug).distinct()
        return query
    
    @staticmethod
    def get_categories(brand_slug=None):
        query = Category.objects.all()
        if brand_slug:
            query = query.filter(products__brand__slug=brand_slug).distinct()
        return query

    @staticmethod
    def get_variants_category(selected_brands, request, selected_attributes, category_slug=None):
        products = ProductVariant.objects.select_related('product').prefetch_related('attribute_variants', 'attribute_variants__attribute').all()

        conditions = Q()

        if category_slug:
            conditions &= Q(product__category__slug=category_slug)

        if selected_brands:
            conditions &= Q(product__brand__slug__in=selected_brands)

        if selected_attributes:

            for attr_slug, values in selected_attributes.items():

                attr_query = Q(attribute_variants__attribute__slug=attr_slug, attribute_variants__value__value_en__in=values)
                products = products.filter(attr_query)

        return products.filter(conditions).distinct()
    
    @staticmethod
    def get_variants_brand(selected_categories, request, selected_attributes, brand_slug=None):
        products = ProductVariant.objects.select_related('product').prefetch_related('attribute_variants', 'attribute_variants__attribute').all()

        conditions = Q()

        if brand_slug:
            conditions &= Q(product__brand__slug=brand_slug)

        if selected_categories:
            conditions &= Q(product__category__slug__in=selected_categories)

        if selected_attributes:

            for attr_slug, values in selected_attributes.items():

                attr_query = Q(attribute_variants__attribute__slug=attr_slug, attribute_variants__value__value_en__in=values)
                products = products.filter(attr_query)

        return products.filter(conditions).distinct()
    
    @staticmethod
    def get_attributes_category(category_slug):
        category = Category.objects.get(slug=category_slug)
        products = Product.objects.filter(category=category)
        variants = ProductVariant.objects.filter(product__in=products)
        attributes = Attribute.objects.filter(attribute_variants__variant__in=variants).distinct()
        attribute_values = AttributeValue.objects.filter(attribute__in=attributes, attribute_variants__variant__in=variants, attribute_variants__is_filter=True).distinct()
        return {
            attribute: attribute_values.filter(attribute=attribute)
            for attribute in attributes
        }
    
    @staticmethod
    def get_attributes_brand(brand_slug):
        brand = Brand.objects.get(slug=brand_slug)
        products = Product.objects.filter(brand=brand)
        variants = ProductVariant.objects.filter(product__in=products)
        attributes = Attribute.objects.filter(attribute_variants__variant__in=variants).distinct()
        attribute_values = AttributeValue.objects.filter(attribute__in=attributes, attribute_variants__variant__in=variants, attribute_variants__is_filter=True).distinct()
        return {
            attribute: attribute_values.filter(attribute=attribute)
            for attribute in attributes
        }