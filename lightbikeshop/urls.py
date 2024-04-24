from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('nested_admin/', include('nested_admin.urls')),
    path('', include(('store.urls', 'store'), namespace='store')),
    path('', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('', include(('cart.urls', 'cart'), namespace='cart')),
    path('', include(('cms.urls', 'cms'), namespace='cms')),
    path('', include(('orders.urls', 'orders'), namespace='orders')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]