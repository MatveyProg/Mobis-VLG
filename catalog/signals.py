from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from catalog.models import Product, ProductCrossNumber
from catalog.vehicles import apply_default_vehicles
from warehouse.models import Stock


@receiver(post_save, sender=Product)
def ensure_stock_and_vehicles(sender, instance, created, **kwargs):
    if created:
        Stock.objects.get_or_create(product=instance)
    apply_default_vehicles(instance)


def _refresh_search_text(product: Product):
    Product.objects.filter(pk=product.pk).update(search_text=product.compose_search_text())


@receiver(post_save, sender=ProductCrossNumber)
def refresh_search_on_cross_save(sender, instance, **kwargs):
    _refresh_search_text(instance.product)


@receiver(post_delete, sender=ProductCrossNumber)
def refresh_search_on_cross_delete(sender, instance, **kwargs):
    if instance.product_id:
        product = Product.objects.filter(pk=instance.product_id).first()
        if product:
            _refresh_search_text(product)
