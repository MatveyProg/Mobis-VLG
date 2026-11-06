from orders.models import Cart, ClientRequest, Order


def cart_counter(request):
    empty = {
        'cart_count': 0,
        'active_orders_count': 0,
        'client_request_count': 0,
        'pending_client_requests_count': 0,
    }
    if not request.user.is_authenticated:
        return empty
    if request.user.is_staff:
        active_orders_count = Order.objects.exclude(
            status__in=[Order.Status.SHIPPED, Order.Status.CANCELLED],
        ).count()
        pending = ClientRequest.objects.filter(status=ClientRequest.Status.SUBMITTED).count()
        return {
            'cart_count': 0,
            'active_orders_count': active_orders_count,
            'client_request_count': 0,
            'pending_client_requests_count': pending,
        }
    try:
        cart_count = request.user.cart.total_quantity
    except Cart.DoesNotExist:
        cart_count = 0
    draft = ClientRequest.objects.filter(
        customer=request.user,
        status=ClientRequest.Status.DRAFT,
    ).first()
    client_request_count = draft.total_quantity if draft else 0
    return {
        'cart_count': cart_count,
        'active_orders_count': 0,
        'client_request_count': client_request_count,
        'pending_client_requests_count': 0,
    }
