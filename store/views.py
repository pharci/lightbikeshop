from django.shortcuts import render, get_object_or_404
from .models import * 
from django.db.models import Q
from django.http import JsonResponse
from django.core.serializers import serialize
from collections import defaultdict
from django.core.paginator import Paginator

def get_brands(category_slug):
    query = Brand.objects.all()
    if category_slug:
        query = query.filter(products__category__slug=category_slug).distinct()
    return query

def get_variants(selected_brands, request, selected_attributes, category_slug=None):
    filter_conditions = Q()

    if category_slug:
        filter_conditions &= Q(product__category__slug=category_slug)
    if selected_brands:
        filter_conditions &= Q(product__brand__slug__in=selected_brands)
    if selected_attributes:
        filter_conditions &= Q(attribute_variants__value__value_en__in=selected_attributes)

    return ProductVariant.objects.select_related('product').prefetch_related('attribute_variants').filter(filter_conditions).distinct()

def get_attribute_variants(category_slug):
    return Attribute.objects.filter(
        attribute_variants__variant__product__category__slug=category_slug,
        attribute_variants__is_filter=True
    ).distinct()

def product_list(request, category_slug=None):
    category = get_object_or_404(Category, slug=category_slug) if category_slug else None

    brands = get_brands(category_slug)
    attributes = get_attribute_variants(category_slug)

    selected_brands = request.GET.getlist('brand')
    selected_attributes = [value for attribute in attributes for value in request.GET.getlist(f'{attribute.slug}')]

    variants = get_variants(selected_brands, request, selected_attributes, category_slug)

    paginator = Paginator(variants, 32)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'category': category,
        'brands': brands,
        'selected_brands': selected_brands,
        'attributes': attributes,
        'selected_attributes': selected_attributes,
        'page_obj': page_obj,
    }

    return render(request, 'store/products_list.html', context)
    

def product_detail(request, category_slug, brand_slug, sku, slug):
    product = get_object_or_404(Product, category__slug=category_slug, brand__slug=brand_slug, variants__sku=sku, slug=slug)

    variant = get_object_or_404(ProductVariant, sku=sku)

    attribute_variants = AttributeVariant.objects.filter(variant=variant)

    images = ProductImage.objects.filter(variant=variant)
    image_urls = [image.get_image_url() for image in images]


    context = {'product': product, 'variant': variant, 'image_urls': image_urls, 'attribute_variants': attribute_variants}
    return render(request, 'store/product_detail.html', context)

def catalog(request):

    categories = Category.objects.all()

    brands = Brand.objects.all()

    return render(request, 'store/catalog.html', {'brands': brands, 'categories': categories})