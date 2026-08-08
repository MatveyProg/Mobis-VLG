from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from catalog.models import Product
from warehouse.forms import (
    RequisitionFromSalesForm,
    RequisitionHeaderForm,
    RequisitionItemForm,
    StockInHeaderForm,
    StockInItemForm,
)
from warehouse.models import (
    PurchaseRequisition,
    PurchaseRequisitionItem,
    StockIn,
    StockInItem,
    Supplier,
)
from warehouse.requisition import (
    REQUISITION_TRANSITIONS,
    build_requisition_from_sales,
    set_requisition_status,
)
from warehouse.exports import export_requisition_xlsx
from warehouse.services import StockError, post_stock_in
from warehouse.utils import get_product_by_sku


def staff_required(user):
    return user.is_authenticated and user.is_staff


def _editable_requisition(requisition):
    return requisition.status in (
        PurchaseRequisition.Status.CREATED,
        PurchaseRequisition.Status.IN_PROGRESS,
    )


@login_required
@user_passes_test(staff_required)
def stock_balances(request):
    products = Product.objects.select_related('stock', 'category').order_by('sku')
    q = request.GET.get('q', '').strip()
    if q:
        from catalog.utils import normalize_code
        from django.db.models import Q
        norm = normalize_code(q)
        products = products.filter(
            Q(sku__icontains=q)
            | Q(sku_normalized__icontains=norm)
            | Q(name_ru__icontains=q)
        )
    only_positive = request.GET.get('positive') == '1'
    rows = []
    for p in products:
        stock = getattr(p, 'stock', None)
        on_hand = stock.quantity_on_hand if stock else 0
        reserved = stock.quantity_reserved if stock else 0
        available = stock.quantity_available if stock else 0
        if only_positive and on_hand <= 0:
            continue
        rows.append({
            'product': p,
            'on_hand': on_hand,
            'reserved': reserved,
            'available': available,
        })
    return render(request, 'warehouse/stock_balances.html', {
        'rows': rows,
        'q': q,
        'positive': only_positive,
    })


# --- Заявки на закупку ---


@login_required
@user_passes_test(staff_required)
def requisition_list(request):
    status = request.GET.get('status', '')
    qs = PurchaseRequisition.objects.select_related('created_by').prefetch_related('items')
    if status:
        qs = qs.filter(status=status)
    return render(request, 'warehouse/requisition_list.html', {
        'requisitions': qs,
        'status': status,
        'status_choices': PurchaseRequisition.Status.choices,
    })


@login_required
@user_passes_test(staff_required)
@require_POST
def requisition_create(request):
    req = PurchaseRequisition.objects.create(
        created_by=request.user,
        status=PurchaseRequisition.Status.CREATED,
    )
    messages.success(request, f'Создана заявка {req.number}.')
    return redirect('warehouse:requisition_detail', pk=req.pk)


@login_required
@user_passes_test(staff_required)
def requisition_from_sales(request):
    form = RequisitionFromSalesForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            req = build_requisition_from_sales(
                date_from=form.cleaned_data['date_from'],
                date_to=form.cleaned_data['date_to'],
                user=request.user,
            )
            count = req.items.count()
            if count == 0:
                messages.warning(request, f'Заявка {req.number} создана, но продаж за период не найдено.')
            else:
                messages.success(request, f'Заявка {req.number}: {count} поз.')
            return redirect('warehouse:requisition_detail', pk=req.pk)
        except Exception as exc:  # noqa: BLE001
            messages.error(request, str(exc))
    return render(request, 'warehouse/requisition_from_sales.html', {'form': form})


@login_required
@user_passes_test(staff_required)
def requisition_detail(request, pk):
    requisition = get_object_or_404(
        PurchaseRequisition.objects.prefetch_related(
            'items__product',
            'status_history',
            'stock_ins__items',
        ),
        pk=pk,
    )
    header_form = RequisitionHeaderForm(instance=requisition)
    item_form = RequisitionItemForm()
    editable = _editable_requisition(requisition)
    status_labels = dict(PurchaseRequisition.Status.choices)
    next_statuses = [
        {'code': code, 'label': status_labels[code]}
        for code in sorted(
            REQUISITION_TRANSITIONS.get(requisition.status, set()),
            key=lambda s: list(PurchaseRequisition.Status.values).index(s),
        )
    ]
    if request.method == 'POST' and request.POST.get('form') == 'header' and editable:
        header_form = RequisitionHeaderForm(request.POST, instance=requisition)
        if header_form.is_valid():
            header_form.save()
            messages.success(request, 'Данные заявки сохранены.')
            return redirect('warehouse:requisition_detail', pk=pk)
    items = list(requisition.items.all())
    total_krw = sum((item.sum_krw for item in items), start=0)
    total_rub = sum((item.sum_rub for item in items), start=0)
    return render(request, 'warehouse/requisition_detail.html', {
        'requisition': requisition,
        'header_form': header_form,
        'item_form': item_form,
        'editable': editable,
        'next_statuses': next_statuses,
        'suppliers': Supplier.objects.order_by('name'),
        'total_krw': total_krw,
        'total_rub': total_rub,
    })


@login_required
@user_passes_test(staff_required)
@require_POST
def requisition_set_status(request, pk):
    requisition = get_object_or_404(PurchaseRequisition, pk=pk)
    new_status = request.POST.get('status', '')
    try:
        set_requisition_status(requisition, new_status, user=request.user)
        messages.success(request, f'Статус: «{requisition.get_status_display()}».')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('warehouse:requisition_detail', pk=pk)


@login_required
@user_passes_test(staff_required)
@require_POST
def requisition_add_item(request, pk):
    requisition = get_object_or_404(PurchaseRequisition, pk=pk)
    if not _editable_requisition(requisition):
        messages.error(request, 'Заявку в этом статусе нельзя редактировать.')
        return redirect('warehouse:requisition_detail', pk=pk)
    form = RequisitionItemForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Проверьте поля строки заявки.')
        return redirect('warehouse:requisition_detail', pk=pk)
    try:
        product = get_product_by_sku(form.cleaned_data['product_sku'])
    except Exception as exc:  # noqa: BLE001
        messages.error(request, str(exc))
        return redirect('warehouse:requisition_detail', pk=pk)
    max_line = requisition.items.aggregate(m=Max('line_number'))['m'] or 0
    PurchaseRequisitionItem.objects.create(
        requisition=requisition,
        line_number=max_line + 1,
        product=product,
        quantity=form.cleaned_data['quantity'],
        purchase_price_rub=product.price_rub,
        purchase_price_krw=product.price_krw,
    )
    messages.success(request, f'Добавлен {product.sku}.')
    return redirect('warehouse:requisition_detail', pk=pk)


@login_required
@user_passes_test(staff_required)
def requisition_export(request, pk):
    requisition = get_object_or_404(
        PurchaseRequisition.objects.prefetch_related('items__product'),
        pk=pk,
    )
    return export_requisition_xlsx(requisition)


@login_required
@user_passes_test(staff_required)
@require_POST
def requisition_delete_item(request, pk, item_pk):
    requisition = get_object_or_404(PurchaseRequisition, pk=pk)
    if not _editable_requisition(requisition):
        messages.error(request, 'Заявку в этом статусе нельзя редактировать.')
        return redirect('warehouse:requisition_detail', pk=pk)
    item = get_object_or_404(PurchaseRequisitionItem, pk=item_pk, requisition=requisition)
    sku = item.product.sku
    item.delete()
    messages.info(request, f'Строка {sku} удалена.')
    return redirect('warehouse:requisition_detail', pk=pk)


@login_required
@user_passes_test(staff_required)
@require_POST
@transaction.atomic
def requisition_receive(request, pk):
    """Create and post partial stock-in from selected requisition lines."""
    requisition = get_object_or_404(
        PurchaseRequisition.objects.prefetch_related('items__product'),
        pk=pk,
    )
    supplier_id = request.POST.get('supplier')
    if not supplier_id:
        messages.error(request, 'Выберите поставщика для прихода.')
        return redirect('warehouse:requisition_detail', pk=pk)
    supplier = get_object_or_404(Supplier, pk=supplier_id)

    lines = []
    for item in requisition.items.all():
        key = f'receive_{item.pk}'
        if request.POST.get(key) != '1':
            continue
        try:
            qty = int(request.POST.get(f'qty_{item.pk}', 0))
        except (TypeError, ValueError):
            qty = 0
        if qty <= 0:
            continue
        if qty > item.quantity_remaining:
            messages.error(
                request,
                f'По {item.product.sku} можно оприходовать не более {item.quantity_remaining} шт.',
            )
            return redirect('warehouse:requisition_detail', pk=pk)
        lines.append((item, qty))

    if not lines:
        messages.error(request, 'Отметьте строки и укажите количество для оприходования.')
        return redirect('warehouse:requisition_detail', pk=pk)

    stock_in = StockIn.objects.create(
        supplier=supplier,
        requisition=requisition,
        created_by=request.user,
        date=timezone.now(),
    )
    for req_item, qty in lines:
        StockInItem.objects.create(
            stock_in=stock_in,
            product=req_item.product,
            quantity=qty,
            purchase_price_rub=req_item.purchase_price_rub,
            requisition_item=req_item,
        )
    try:
        post_stock_in(stock_in, user=request.user)
    except StockError as exc:
        messages.error(request, str(exc))
        return redirect('warehouse:stock_in_detail', pk=stock_in.pk)

    messages.success(request, f'Приход #{stock_in.pk} проведён ({len(lines)} поз.).')
    return redirect('warehouse:requisition_detail', pk=pk)


# --- Приходы ---


@login_required
@user_passes_test(staff_required)
def stock_in_list(request):
    posted = request.GET.get('posted', '')
    qs = StockIn.objects.select_related('supplier', 'requisition', 'created_by')
    if posted == '1':
        qs = qs.filter(is_posted=True)
    elif posted == '0':
        qs = qs.filter(is_posted=False)
    return render(request, 'warehouse/stock_in_list.html', {
        'stock_ins': qs,
        'posted': posted,
    })


@login_required
@user_passes_test(staff_required)
def stock_in_create(request):
    initial = {'date': timezone.localtime().replace(second=0, microsecond=0)}
    requisition_id = request.GET.get('requisition')
    if requisition_id:
        initial['requisition'] = requisition_id
    form = StockInHeaderForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        stock_in = form.save(commit=False)
        stock_in.created_by = request.user
        stock_in.is_posted = False
        stock_in.save()
        messages.success(request, f'Создан приход #{stock_in.pk}. Добавьте строки.')
        return redirect('warehouse:stock_in_detail', pk=stock_in.pk)
    return render(request, 'warehouse/stock_in_form.html', {
        'form': form,
        'title': 'Новый приход',
    })


@login_required
@user_passes_test(staff_required)
def stock_in_detail(request, pk):
    stock_in = get_object_or_404(
        StockIn.objects.select_related('supplier', 'requisition').prefetch_related('items__product'),
        pk=pk,
    )
    item_form = StockInItemForm()
    header_form = None
    if not stock_in.is_posted:
        header_form = StockInHeaderForm(instance=stock_in)
        if request.method == 'POST' and request.POST.get('form') == 'header':
            header_form = StockInHeaderForm(request.POST, instance=stock_in)
            if header_form.is_valid():
                header_form.save()
                messages.success(request, 'Шапка прихода сохранена.')
                return redirect('warehouse:stock_in_detail', pk=pk)
    return render(request, 'warehouse/stock_in_detail.html', {
        'stock_in': stock_in,
        'item_form': item_form,
        'header_form': header_form,
        'editable': not stock_in.is_posted,
    })


@login_required
@user_passes_test(staff_required)
@require_POST
def stock_in_add_item(request, pk):
    stock_in = get_object_or_404(StockIn, pk=pk)
    if stock_in.is_posted:
        messages.error(request, 'Проведённый документ нельзя изменять.')
        return redirect('warehouse:stock_in_detail', pk=pk)
    form = StockInItemForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Проверьте поля строки прихода.')
        return redirect('warehouse:stock_in_detail', pk=pk)
    try:
        product = get_product_by_sku(form.cleaned_data['product_sku'])
    except Exception as exc:  # noqa: BLE001
        messages.error(request, str(exc))
        return redirect('warehouse:stock_in_detail', pk=pk)
    StockInItem.objects.create(
        stock_in=stock_in,
        product=product,
        quantity=form.cleaned_data['quantity'],
        purchase_price_rub=form.cleaned_data['purchase_price_rub'],
    )
    messages.success(request, f'Добавлен {product.sku}.')
    return redirect('warehouse:stock_in_detail', pk=pk)


@login_required
@user_passes_test(staff_required)
@require_POST
def stock_in_delete_item(request, pk, item_pk):
    stock_in = get_object_or_404(StockIn, pk=pk)
    if stock_in.is_posted:
        messages.error(request, 'Проведённый документ нельзя изменять.')
        return redirect('warehouse:stock_in_detail', pk=pk)
    item = get_object_or_404(StockInItem, pk=item_pk, stock_in=stock_in)
    item.delete()
    messages.info(request, 'Строка удалена.')
    return redirect('warehouse:stock_in_detail', pk=pk)


@login_required
@user_passes_test(staff_required)
@require_POST
def stock_in_post(request, pk):
    stock_in = get_object_or_404(StockIn, pk=pk)
    try:
        post_stock_in(stock_in, user=request.user)
        messages.success(request, f'Приход #{pk} проведён. Остатки обновлены.')
    except StockError as exc:
        messages.error(request, str(exc))
    return redirect('warehouse:stock_in_detail', pk=pk)
