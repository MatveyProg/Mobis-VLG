from django.db.models.signals import pre_delete
from django.dispatch import receiver

from warehouse.models import StockIn
from warehouse.services import reverse_stock_in_on_delete


@receiver(pre_delete, sender=StockIn)
def stock_in_pre_delete(sender, instance, **kwargs):
    reverse_stock_in_on_delete(instance)
