from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.conf.urls.static import static
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('orders/', include('orders.urls')),
    path('warehouse/', include('warehouse.urls')),
    path('reports/', include('reports.urls')),
    path('', include('pages.urls')),
    path('', include('catalog.urls')),
]

admin.site.site_header = f'{settings.SHOP_NAME} — администрирование'
admin.site.site_title = settings.SHOP_NAME
admin.site.index_title = 'Панель управления'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.SERVE_MEDIA:
    urlpatterns += [
        re_path(
            r'^media/(?P<path>.*)$',
            serve,
            {'document_root': settings.MEDIA_ROOT},
        ),
    ]
