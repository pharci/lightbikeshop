from django.shortcuts import render, get_object_or_404
from .models import Wheel, FAQ, Page, SocialLink
from cart.models import PickupPoint
from products.models import Brand, Variant

 
def home(request):
    wheel = Wheel.objects.filter(is_active=True).order_by("order")
    brands = Brand.objects.all()
    variants_rec = Variant.objects.filter(rec=True, inventory__gt=0)[:20]
    variants_new = Variant.objects.filter(new=True, inventory__gt=0)[:20]
    pickups = PickupPoint.objects.filter(is_main=True).order_by("city", "sort", "title")

    social_links = SocialLink.objects.all()
    social_tg = SocialLink.objects.filter(title__iexact="Telegram").first()

    return render(request, "core/home.html", {
        "wheel": wheel,
        "brands": brands,
        "variants_rec": variants_rec,
        "variants_new": variants_new,
        "pickups": pickups,
        "social_links": social_links,
    })

def faq(request):
    faqs = FAQ.objects.filter(is_active=True).order_by("order")
    return render(request, "core/faq.html", {"faqs": faqs})


def page_detail(request, slug):
    page = get_object_or_404(Page, slug=slug, is_published=True, external_url="")
    ctx = {"page": page}
    return render(request, "core/detail.html", ctx)