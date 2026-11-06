from collections import defaultdict
from datetime import datetime, time

from django.db.models import Sum
from django.utils import timezone

from orders.models import ClientRequest, ClientRequestItem, Order, OrderItem
from catalog.models import Product
from warehouse.models import (
    PurchaseRequisition,
    PurchaseRequisitionItem,
    PurchaseRequisitionStatusHistory,
    StockOutItem,
)


def build_requisition_from_sales(*, date_from, date_to, user=None) -> PurchaseRequisition:
    """Create purchase requisition lines from confirmed sales and accepted client requests."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(date_from, time.min), tz)
    end = timezone.make_aware(datetime.combine(date_to, time.max), tz)

    sales_rows = (
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
    sales_by_product = {row['product_id']: row['qty'] for row in sales_rows}

    out_rows = (
        StockOutItem.objects.filter(
            stock_out__is_posted=True,
            stock_out__date__gte=start,
            stock_out__date__lte=end,
        )
        .values('product_id')
        .annotate(qty=Sum('quantity'))
        .order_by()
    )
    out_by_product = {row['product_id']: row['qty'] for row in out_rows}

    preorder_items = list(
        ClientRequestItem.objects.filter(
            request__status=ClientRequest.Status.ACCEPTED,
            allocated_requisition__isnull=True,
        ).select_related('request', 'request__customer', 'product')
    )
    pre_by_product: dict[int, list[ClientRequestItem]] = defaultdict(list)
    for item in preorder_items:
        pre_by_product[item.product_id].append(item)

    product_ids = set(sales_by_product) | set(pre_by_product) | set(out_by_product)

    requisition = PurchaseRequisition.objects.create(
        created_by=user,
        status=PurchaseRequisition.Status.CREATED,
        note=f'Автоформирование по расходу {date_from} — {date_to} и принятым заявкам клиентов',
    )

    for line_no, product_id in enumerate(sorted(product_ids), start=1):
        product = Product.objects.get(pk=product_id)
        notes = []
        quantity = 0
        sold = sales_by_product.get(product_id) or 0
        if sold:
            quantity += sold
            notes.append(f'продажи: {sold} шт')
        written_off = out_by_product.get(product_id) or 0
        if written_off:
            quantity += written_off
            notes.append(f'расход: {written_off} шт')
        for item in pre_by_product.get(product_id, []):
            quantity += item.quantity
            notes.append(f'{item.request.customer_display}: {item.quantity} шт')
        PurchaseRequisitionItem.objects.create(
            requisition=requisition,
            line_number=line_no,
            product=product,
            quantity=quantity,
            purchase_price_krw=product.purchase_price_krw,
            purchase_price_rub=product.purchase_price_rub,
            source_note='; '.join(notes),
        )

    if preorder_items:
        ClientRequestItem.objects.filter(
            pk__in=[item.pk for item in preorder_items],
        ).update(allocated_requisition=requisition)

    return requisition


def renumber_requisition_items(requisition: PurchaseRequisition) -> None:
    items = list(requisition.items.order_by('line_number', 'id'))
    for index, item in enumerate(items, start=1):
        if item.line_number != index:
            item.line_number = index
            item.save(update_fields=['line_number'])


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
