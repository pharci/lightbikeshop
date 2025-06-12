from django.urls import include, re_path, path

from . import views

urlpatterns = [
	#Leave as empty string for base url
    path('catalog/', views.catalog, name="catalog"),
	re_path(r'^products/search/$', views.product_list, name='search'),

    re_path(r'^products/(?P<category>[-\w]+)/$',
        views.product_list,
        name='product_list_by_category'),

    re_path(r'^brands/(?P<brand>[-\w]+)/$',
        views.product_list,
        name='product_list_by_brand'),

    re_path(r'^products/(?P<category_slug>[-\w]+)/(?P<id>\d+)/(?P<slug>[-\w]+)/$',
        views.product_detail,
        name='product_detail'),
]