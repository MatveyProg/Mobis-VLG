from django.core.exceptions import ValidationError

from catalog.models import Product
from catalog.utils import normalize_code


def get_product_by_sku(sku: str) -> Product:
    raw = (sku or '').strip()
    if not raw:
        raise ValidationError('Укажите артикул товара.')
    norm = normalize_code(raw)
    product = Product.objects.filter(sku_normalized=norm).first()
    if not product:
        product = Product.objects.filter(sku__iexact=raw).first()
    if not product:
        raise ValidationError(f'Товар с артикулом «{raw}» не найден.')
    return product
