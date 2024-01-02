from django.urls import include, re_path, path

from . import views

urlpatterns = [
    #Leave as empty string for base url
    path('catalog/', views.catalog, name="catalog"),
    re_path(r'^products/search/$', views.product_list, name='search'),

    path('products/', views.product_list, name='product_list'),
    path('products/<slug:category_slug>', views.product_list, name='product_list'),

    re_path(r'^products/(?P<category_slug>[-\w]+)/(?P<brand_slug>[-\w]+)/(?P<sku>[-\w]+)/(?P<slug>[-\w]+)/$',
        views.product_detail,
        name='product_detail'),
]