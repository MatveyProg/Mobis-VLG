from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from catalog.models import Product
from warehouse.models import Stock, StockIn, StockMovement


class StockError(ValidationError):
    pass


def get_or_create_stock(product: Product) -> Stock:
    stock, _ = Stock.objects.get_or_create(product=product)
    return stock


def _lock_stock(product_id: int) -> Stock:
    stock, _ = Stock.objects.select_for_update().get_or_create(product_id=product_id)
    return stock


@transaction.atomic
def reserve(product_id: int, quantity: int, *, order=None, user=None, comment=''):
    if quantity <= 0:
        raise StockError('Количество должно быть больше нуля.')
    stock = _lock_stock(product_id)
    if stock.quantity_available < quantity:
        raise StockError(
            f'Недостаточно доступного остатка для «{stock.product.sku}». '
            f'Доступно: {stock.quantity_available}, запрошено: {quantity}.'
        )
    stock.quantity_reserved = F('quantity_reserved') + quantity
    stock.save(update_fields=['quantity_reserved'])
    stock.refresh_from_db()
    StockMovement.objects.create(
        product_id=product_id,
        movement_type=StockMovement.MovementType.RESERVE,
        quantity=quantity,
        user=user,
        order=order,
        comment=comment or 'Резерв под заказ',
    )
    return stock


@transaction.atomic
def unreserve(product_id: int, quantity: int, *, order=None, user=None, comment=''):
    if quantity <= 0:
        raise StockError('Количество должно быть больше нуля.')
    stock = _lock_stock(product_id)
    if stock.quantity_reserved < quantity:
        raise StockError('Нельзя снять резерв больше текущего.')
    stock.quantity_reserved = F('quantity_reserved') - quantity
    stock.save(update_fields=['quantity_reserved'])
    stock.refresh_from_db()
    StockMovement.objects.create(
        product_id=product_id,
        movement_type=StockMovement.MovementType.UNRESERVE,
        quantity=quantity,
        user=user,
        order=order,
        comment=comment or 'Снятие резерва',
    )
    return stock


@transaction.atomic
def confirm_sale(product_id: int, quantity: int, *, order=None, user=None, comment=''):
    """Convert reserve into physical OUT."""
    if quantity <= 0:
        raise StockError('Количество должно быть больше нуля.')
    stock = _lock_stock(product_id)
    if stock.quantity_reserved < quantity:
        raise StockError('Недостаточно резерва для подтверждения.')
    if stock.quantity_on_hand < quantity:
        raise StockError('Недостаточно физического остатка для списания.')
    stock.quantity_reserved = F('quantity_reserved') - quantity
    stock.quantity_on_hand = F('quantity_on_hand') - quantity
    stock.save(update_fields=['quantity_reserved', 'quantity_on_hand'])
    stock.refresh_from_db()
    StockMovement.objects.create(
        product_id=product_id,
        movement_type=StockMovement.MovementType.OUT,
        quantity=quantity,
        user=user,
        order=order,
        comment=comment or 'Расход по заказу',
    )
    return stock


@transaction.atomic
def storno_sale(product_id: int, quantity: int, *, order=None, user=None, comment=''):
    if quantity <= 0:
        raise StockError('Количество должно быть больше нуля.')
    stock = _lock_stock(product_id)
    stock.quantity_on_hand = F('quantity_on_hand') + quantity
    stock.save(update_fields=['quantity_on_hand'])
    stock.refresh_from_db()
    StockMovement.objects.create(
        product_id=product_id,
        movement_type=StockMovement.MovementType.STORNO_OUT,
        quantity=quantity,
        user=user,
        order=order,
        comment=comment or 'Сторно расхода',
    )
    return stock


@transaction.atomic
def post_stock_in(stock_in: StockIn, *, user=None):
    if stock_in.is_posted:
        raise StockError('Документ уже проведён.')
    if not stock_in.items.exists():
        raise StockError('В приходе нет строк.')

    # Validate partial receipt against requisition lines
    for item in stock_in.items.select_related('requisition_item', 'product'):
        if item.requisition_item_id:
            remaining = item.requisition_item.quantity_remaining
            if item.quantity > remaining:
                raise StockError(
                    f'По строке заявки «{item.product.sku}» можно оприходовать '
                    f'не более {remaining} шт.'
                )

    for item in stock_in.items.select_related('product'):
        stock = _lock_stock(item.product_id)
        stock.quantity_on_hand = F('quantity_on_hand') + item.quantity
        stock.save(update_fields=['quantity_on_hand'])
        StockMovement.objects.create(
            product_id=item.product_id,
            movement_type=StockMovement.MovementType.IN,
            quantity=item.quantity,
            user=user,
            stock_in=stock_in,
            comment=f'Приход #{stock_in.pk}',
        )

    stock_in.is_posted = True
    stock_in.save(update_fields=['is_posted'])
    return stock_in


def notify_order_created(order):
    """Extension point for Telegram notifications in v2."""
    return None
