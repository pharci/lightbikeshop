from django.urls import path, re_path
from . import views
from .taobao_api import import_taobao_products

app_name = "products"

urlpatterns = [
    path("api/integrations/taobao/products/", import_taobao_products, name="taobao-import"),
    re_path(r"^catalog/$", views.catalog, name="catalog"),
    re_path(r"^brands/$", views.brands, name="brands"),
    re_path(r"^catalog/search/$", views.list, name="search"),

    re_path(
        r"^catalog/(?P<category_path>.+)/p/(?P<slug>[-\w\.]+)/$",
        views.detail,
        name="detail",
    ),

    re_path(
        r"^catalog/(?P<category_path>.+)/$",
        views.list,
        name="category",
    ),

    re_path(r"^brand/(?P<brand>[-\w]+)/$", views.list, name="brand"),
]
