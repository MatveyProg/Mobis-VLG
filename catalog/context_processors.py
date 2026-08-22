from django.conf import settings

from catalog.models import CarMake


def shop_settings(request):
    return {
        'SHOP_NAME': settings.SHOP_NAME,
        'search_makes': CarMake.objects.all(),
    }
