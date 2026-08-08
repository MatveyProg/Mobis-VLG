from datetime import datetime, time

from django.db.models import Sum
from django.utils import timezone

from orders.models import Order, OrderItem
from catalog.models import Product
from warehouse.models import PurchaseRequisition, PurchaseRequisitionItem, PurchaseRequisitionStatusHistory


def build_requisition_from_sales(*, date_from, date_to, user=None) -> PurchaseRequisition:
    """Create purchase requisition lines from confirmed sales in period."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(date_from, time.min), tz)
    end = timezone.make_aware(datetime.combine(date_to, time.max), tz)

    qs = (
        OrderItem.objects.filter(
            order__status__in=[
                Order.Status.CONFIRMED,
                Order.Status.ASSEMBLED,
                Order.Status.SHIPPED,
            ],
            order__status_changed_at__gte=start,
            order__status_changed_at__lte=end,
        )
        .values('product_id')
        .annotate(qty=Sum('quantity'))
        .order_by()
    )

    requisition = PurchaseRequisition.objects.create(
        created_by=user,
        status=PurchaseRequisition.Status.CREATED,
        note=f'Автоформирование по расходу {date_from} — {date_to}',
    )
    for i, row in enumerate(qs, start=1):
        product = Product.objects.get(pk=row['product_id'])
        PurchaseRequisitionItem.objects.create(
            requisition=requisition,
            line_number=i,
            product=product,
            quantity=row['qty'],
            purchase_price_krw=product.price_krw,
            purchase_price_rub=product.price_rub,
        )
    return requisition


REQUISITION_TRANSITIONS = {
    PurchaseRequisition.Status.CREATED: {
        PurchaseRequisition.Status.IN_PROGRESS,
        PurchaseRequisition.Status.RECEIVED,
    },
    PurchaseRequisition.Status.IN_PROGRESS: {
        PurchaseRequisition.Status.RECEIVED,
    },
    PurchaseRequisition.Status.RECEIVED: set(),
}


def set_requisition_status(requisition: PurchaseRequisition, new_status: str, *, user=None):
    old = requisition.status
    if new_status == old:
        return requisition
    allowed = REQUISITION_TRANSITIONS.get(old, set())
    if new_status not in allowed:
        labels = dict(PurchaseRequisition.Status.choices)
        raise ValueError(
            f'Переход «{labels.get(old, old)}» → «{labels.get(new_status, new_status)}» запрещён.'
        )
    requisition.status = new_status
    requisition.save(update_fields=['status'])
    PurchaseRequisitionStatusHistory.objects.create(
        requisition=requisition,
        previous_status=old,
        new_status=new_status,
        user=user,
    )
    return requisition
