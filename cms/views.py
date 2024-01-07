from django.shortcuts import render, get_object_or_404
from .models import SliderImage
from store.models import Brand, Product

 
def news(request):
	sliderimages = SliderImage.objects.all()

	brands = Brand.objects.all()

	products = Product.objects.filter()

	context = {'sliderimages': sliderimages, "brands": brands, 'products': products}

	return render(request, 'cms/news.html', context)

def faq(request):
	
	return render(request, 'cms/faq.html')