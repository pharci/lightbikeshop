from django.shortcuts import render, get_object_or_404
from .models import * 
from django.db.models import Q
from django.http import JsonResponse

def product_list(request, category=None, brand=None):

	context = {}

	if category:

		category = get_object_or_404(Category, slug=category)

		products = Product.objects.filter(category=category)

		context = {'category': category}

	if brand:
		brand = get_object_or_404(Brand, slug=brand)
		products = Product.objects.filter(brand=brand)

		context = {'brand': brand}

	if request.method == 'GET' and not(brand) and not(category):
		query = request.GET.get('q')
		products = Product.objects.filter(name__icontains=query)


	if products: 
		context['products'] = products

	else:
		notfound = True

		context = {'notfound': notfound}

	return render(request,'products/products_list.html', context)


def product_detail(request, category_slug, id, slug):

	product = get_object_or_404(Product, id=id, slug=slug)

	context = {'product': product}

	return render(request, 'products/product_detail.html', context)

def catalog(request):

	brands = Brand.objects.all()

	return render(request, 'products/catalog.html', {'brands': brands})