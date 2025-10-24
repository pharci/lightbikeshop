from django.contrib import admin
from django.urls import re_path, path, include
from django.conf.urls.static import static
from django.conf import settings
from core.dashboard.admin_index import admin_index

urlpatterns = [
    path("admin/", admin_index, name="admin-index"),
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