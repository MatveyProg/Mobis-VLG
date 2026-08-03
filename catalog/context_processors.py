from django.conf import settings


def shop_settings(request):
    return {
        'SHOP_NAME': settings.SHOP_NAME,
    }
