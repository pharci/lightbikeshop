from django.shortcuts import render, get_object_or_404
from .models import * 
from django.db.models import Q
from django.http import JsonResponse
from django.core.serializers import serialize
from collections import defaultdict

def product_list(request, category_slug=None):
    category = None
    products = Product.objects.all()
    variants = ProductVariant.objects.all()
    brands = Brand.objects.all()
    attribute_values = AttributeValue.objects.all().order_by('attribute__name').distinct()
    print(attribute_values)

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)
        brands = Brand.objects.filter(product__category=category).distinct()
        attribute_values = AttributeValue.objects.filter(
            variant__product__category=category).order_by('attribute__name').distinct()

    selected_brands = request.GET.getlist('brand')

    if selected_brands:
        products = products.filter(brand__slug__in=selected_brands)

    selected_attributes = request.GET.getlist('attribute')
    if selected_attributes:
        products = products.filter(
            variants__attributes__value__in=selected_attributes
        ).distinct()

    grouped_attributes = defaultdict(list)
    for attr_value in attribute_values:
        grouped_attributes[attr_value.attribute.name].append(attr_value.value)

    grouped_attributes = {key: list(set(values)) for key, values in grouped_attributes.items()}

    return render(request, 'products/products_list.html', {
        'products': products,
        'category': category,
        'brands': brands,
        'selected_brands': selected_brands,
        'grouped_attributes': dict(grouped_attributes),
        'selected_attributes': selected_attributes,
    })
    

def product_detail(request, category_slug, brand_slug, sku, slug):
    product = get_object_or_404(Product, category__slug=category_slug, brand__slug=brand_slug, variants__sku=sku, slug=slug)

    variant = get_object_or_404(ProductVariant, sku=sku)

    attributes = AttributeValue.objects.filter(variant=variant)

    images = ProductImage.objects.filter(variant=variant)
    image_urls = [image.get_image_url() for image in images]


    context = {'product': product, 'variant': variant, 'image_urls': image_urls, 'attributes': attributes}
    return render(request, 'products/product_detail.html', context)

def catalog(request):

	brands = Brand.objects.all()

	return render(request, 'products/catalog.html', {'brands': brands})