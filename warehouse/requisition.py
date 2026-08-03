from datetime import datetime, time

from django.db.models import Sum
from django.utils import timezone

from orders.models import Order, OrderItem
from warehouse.models import PurchaseRequisition, PurchaseRequisitionItem


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
        PurchaseRequisitionItem.objects.create(
            requisition=requisition,
            line_number=i,
            product_id=row['product_id'],
            quantity=row['qty'],
        )
    return requisition
