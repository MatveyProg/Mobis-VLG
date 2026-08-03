from orders.models import Cart, Order


def cart_counter(request):
    if not request.user.is_authenticated:
        return {'cart_count': 0, 'active_orders_count': 0}
    active_orders_count = 0
    if request.user.is_staff:
        active_orders_count = Order.objects.exclude(
            status__in=[Order.Status.SHIPPED, Order.Status.CANCELLED],
        ).count()
        return {'cart_count': 0, 'active_orders_count': active_orders_count}
    try:
        cart_count = request.user.cart.total_quantity
    except Cart.DoesNotExist:
        cart_count = 0
    return {'cart_count': cart_count, 'active_orders_count': 0}
