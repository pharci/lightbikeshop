from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path("admin/", include("admin_panel.urls")),
    path('admin/', admin.site.urls),
    path('', include(('core.urls', 'core'), namespace='core')),
    path('', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('', include(('products.urls', 'products'), namespace='products')),
    path('', include(('cart.urls', 'cart'), namespace='cart')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]