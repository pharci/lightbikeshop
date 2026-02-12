from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from products.models import Category, Variant, Brand


class StaticViewSitemap(Sitemap):
    priority = 0.6
    changefreq = "weekly"

    def items(self):
        return [
            reverse("core:home"),
            reverse("products:catalog"),
            reverse("products:brands"),
        ]

    def location(self, item):
        return item


class CategorySitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return Category.objects.all()

    def location(self, obj):
        return obj.get_absolute_url()


class ProductSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Variant.objects.filter(is_active=True)

    def location(self, obj):
        return obj.get_absolute_url()


class BrandSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Brand.objects.all()

    def location(self, obj):
        return f"/brand/{obj.slug}/"
