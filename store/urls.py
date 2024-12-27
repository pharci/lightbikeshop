from django.urls import path, re_path
from .views import *

urlpatterns = [
    path('catalog/', catalog, name="catalog"),
    path('brands/', brands, name="brands"),
    path('brands/<slug:brand_slug>/', ProductListBrandView.as_view(), name='brands'),
    path('wishlist/', WishlistView.as_view(), name="wishlist"),
    path('catalog/search/', ProductListCategoryView.as_view(), name='search'),
    path('catalog/<slug:category_slug>/', ProductListCategoryView.as_view(), name='catalog'),
    re_path(r'^catalog/(?P<category_slug>[-\w]+)/(?P<brand_slug>[-\w]+)/(?P<slug>[-\w]+)/(?P<sku>[-\w]+)/$', product_detail, name='product_detail'),
    path('add_to_wishlist/<int:variant_id>/', add_to_wishlist, name='add_to_wishlist'),
]