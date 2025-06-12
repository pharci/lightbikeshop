from django.shortcuts import render, get_object_or_404
from .models import Wheel
from products.models import Brand, Product

 
def news(request):
	photos = Wheel.objects.all()

	brands = Brand.objects.all()

	products = Product.objects.filter(rec=True)

	context = {'photos': photos, "brands": brands, 'products': products}

	return render(request, 'store/news.html', context)

def faq(request):
	
	return render(request, 'store/faq.html')