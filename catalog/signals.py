from django.db.models.signals import post_save
from django.dispatch import receiver

from catalog.models import Product
from warehouse.models import Stock


@receiver(post_save, sender=Product)
def ensure_stock(sender, instance, created, **kwargs):
    if created:
        Stock.objects.get_or_create(product=instance)
