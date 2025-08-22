from django.shortcuts import render, get_object_or_404
from .models import Wheel, FAQ
from cart.models import PickupPoint
from products.models import Brand, Variant

 
def home(request):
    wheel = Wheel.objects.filter(is_active=True).order_by("order")
    brands = Brand.objects.all()
    mods = Variant.objects.filter(rec=True)
    pickups = PickupPoint.objects.filter(is_main=True).order_by("city", "sort", "title")
    return render(request, "core/home.html", {
        "wheel": wheel, "brands": brands, "mods": mods, "pickups": pickups,
    })

def faq(request):
    faqs = FAQ.objects.filter(is_active=True).order_by("order")
    return render(request, "core/faq.html", {"faqs": faqs})