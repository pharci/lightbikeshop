from django.urls import path
from . import views

app_name = "products"

urlpatterns = [
    path("catalog/", views.catalog, name="catalog"),
    path("catalog/search/", views.list, name="search"),

    # важно: detail идёт раньше category
    path(
        "catalog/<path:category_path>/<slug:slug>/<int:variant_id>/",
        views.detail,
        name="detail",
    ),
    path(
        "catalog/<path:category_path>/",
        views.list,
        name="category",
    ),

    path("brands/<slug:brand>/", views.list, name="brand"),
]