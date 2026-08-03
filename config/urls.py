from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('orders/', include('orders.urls')),
    path('warehouse/', include('warehouse.urls')),
    path('pages/', include('pages.urls')),
    path('', include('catalog.urls')),
    path('reports/', include('reports.urls')),
]

admin.site.site_header = f'{settings.SHOP_NAME} — администрирование'
admin.site.site_title = settings.SHOP_NAME
admin.site.index_title = 'Панель управления'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
