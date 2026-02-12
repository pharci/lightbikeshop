from django.shortcuts import render, get_object_or_404, redirect
from .models import Wheel, FAQ, Page, SocialLink
from cart.models import PickupPoint
from products.models import Brand, Variant
from .sanitize import clean_html
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from django.http import HttpResponse
 
def home(request):
    wheel = Wheel.objects.filter(is_active=True).order_by("order")
    brands = Brand.objects.all()
    variants_rec = Variant.objects.filter(rec=True, inventory__gt=0)[:20]
    variants_new = Variant.objects.filter(new=True, inventory__gt=0)[:20]
    pickups = PickupPoint.objects.filter(is_main=True).order_by("city", "sort", "title")

    social_links = SocialLink.objects.all()

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
    page = get_object_or_404(Page, slug=slug, is_published=True)
    if page.external_url:
        return redirect(page.external_url, permanent=False)
    body = mark_safe(clean_html(page.body or ""))
    return render(request, "core/detail.html", {"page": page, "body": body})



def robots_txt(request):
    return HttpResponse(
        render_to_string("robots.txt"),
        content_type="text/plain"
    )