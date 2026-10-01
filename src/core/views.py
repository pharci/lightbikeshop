from django.shortcuts import render, get_object_or_404, redirect
from .models import Wheel, FAQ, Page, SocialLink
from cart.models import PickupPoint
from products.models import Brand, Variant
from .sanitize import clean_html
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_sameorigin
import requests
 
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


@staff_member_required
def taobao_parser(request):
    return render(request, "core/taobao_parser.html", {
        "parser_url": "/taobao-parser/proxy/",
    })


@csrf_exempt
@xframe_options_sameorigin
@staff_member_required
def taobao_parser_proxy(request, path=""):
    upstream = f"http://127.0.0.1:18765/{path}"
    headers = {}
    for name in ("Content-Type", "X-Requested-With"):
        if request.headers.get(name):
            headers[name] = request.headers[name]
    try:
        response = requests.request(
            request.method,
            upstream,
            params=request.GET,
            data=request.body or None,
            headers=headers,
            timeout=120,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        return HttpResponse(f"Парсер Taobao недоступен: {exc}", status=502)

    body = response.content
    content_type = response.headers.get("Content-Type", "application/octet-stream")
    if content_type.startswith(("text/", "application/json")):
        text = body.decode(response.encoding or "utf-8", errors="replace")
        # Keep the nested /api/browser/ route out of the two generic rewrites.
        # Otherwise it is prefixed twice and the dashboard receives a local 404.
        browser_api_marker = "__TAOBAO_BROWSER_API__/"
        text = text.replace("/api/browser/", browser_api_marker)
        for original, proxied in (
            ("/browser/", "/taobao-parser/proxy/browser/"),
            ("/download/", "/taobao-parser/proxy/download/"),
            ("/api/", "/taobao-parser/proxy/api/"),
        ):
            text = text.replace(original, proxied)
        text = text.replace(browser_api_marker, "/taobao-parser/proxy/api/browser/")
        body = text.encode("utf-8")
        content_type = content_type.replace(response.encoding or "utf-8", "utf-8")

    result = HttpResponse(body, status=response.status_code, content_type=content_type)
    if response.headers.get("Content-Disposition"):
        result["Content-Disposition"] = response.headers["Content-Disposition"]
    return result
