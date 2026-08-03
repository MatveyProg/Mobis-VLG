from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from orders.models import Order, OrderItem, OrderStatusHistory
from warehouse import services as stock_services
from warehouse.services import StockError, notify_order_created


class OrderError(ValidationError):
    pass


@transaction.atomic
def create_order_from_cart(*, user, cart, form_data) -> Order:
    items = list(cart.items.select_related('product', 'product__stock'))
    if not items:
        raise OrderError('Корзина пуста.')

    delivery_method = form_data['delivery_method']
    delivery_address = form_data.get('delivery_address', '').strip()
    if delivery_method == Order.DeliveryMethod.DELIVERY and not delivery_address:
        raise OrderError('Укажите адрес доставки.')

    order = Order.objects.create(
        customer=user,
        customer_name=form_data['customer_name'].strip(),
        phone=form_data['phone'].strip(),
        messenger=form_data['messenger'],
        messenger_contact=form_data['messenger_contact'].strip(),
        delivery_method=delivery_method,
        delivery_address=delivery_address,
        comment=form_data.get('comment', '').strip(),
        status=Order.Status.NEW,
    )

    for cart_item in items:
        product = cart_item.product
        if not product.is_active:
            raise OrderError(f'Товар «{product.sku}» недоступен для заказа.')
        stock_services.reserve(
            product.id,
            cart_item.quantity,
            order=order,
            user=user,
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=cart_item.quantity,
            price_rub=product.price_rub,
        )

    OrderStatusHistory.objects.create(
        order=order,
        previous_status='',
        new_status=Order.Status.NEW,
        user=user,
    )
    cart.items.all().delete()
    notify_order_created(order)
    return order


@transaction.atomic
def change_order_status(order: Order, new_status: str, *, user=None) -> Order:
    old_status = order.status
    if new_status == old_status:
        return order

    allowed = Order.ALLOWED_TRANSITIONS.get(old_status, set())
    if new_status not in allowed:
        raise OrderError(
            f'Переход «{order.get_status_display()}» → '
            f'«{dict(Order.Status.choices).get(new_status, new_status)}» запрещён.'
        )

    items = list(order.items.select_related('product'))

    try:
        if old_status == Order.Status.NEW and new_status == Order.Status.CONFIRMED:
            for item in items:
                stock_services.confirm_sale(
                    item.product_id,
                    item.quantity,
                    order=order,
                    user=user,
                )
        elif new_status == Order.Status.CANCELLED:
            if old_status == Order.Status.NEW:
                for item in items:
                    stock_services.unreserve(
                        item.product_id,
                        item.quantity,
                        order=order,
                        user=user,
                    )
            elif old_status in (Order.Status.CONFIRMED, Order.Status.ASSEMBLED):
                for item in items:
                    stock_services.storno_sale(
                        item.product_id,
                        item.quantity,
                        order=order,
                        user=user,
                    )
    except StockError as exc:
        raise OrderError(exc.messages if hasattr(exc, 'messages') else exc) from exc

    order.status = new_status
    order.status_changed_at = timezone.now()
    order.save(update_fields=['status', 'status_changed_at'])
    OrderStatusHistory.objects.create(
        order=order,
        previous_status=old_status,
        new_status=new_status,
        user=user,
    )
    return order
