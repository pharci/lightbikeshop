from django.urls import re_path
from . import views

app_name = "products"

urlpatterns = [
    re_path(r"^catalog/$", views.catalog, name="catalog"),
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

    re_path(r"^brands/(?P<brand>[-\w]+)/$", views.list, name="brand"),
]
