from django.shortcuts import render, get_object_or_404
from .models import SliderImage
from store.models import Brand, ProductVariant

 
def news(request):
    sliderimages = SliderImage.objects.all()
    brands = Brand.objects.all()
    recommended_variants = ProductVariant.objects.filter(recommendation=True)

    context = {
        'sliderimages': sliderimages,
        'brands': brands,
        'rec': recommended_variants
    }

    return render(request, 'cms/news.html', context)

def faq(request):
	
	return render(request, 'cms/faq.html')