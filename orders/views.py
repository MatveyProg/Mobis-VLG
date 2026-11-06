from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, FormView, ListView

from catalog.models import Product
from orders.forms import AddToCartForm, CheckoutForm
from orders.models import Cart, CartItem, ClientRequest, ClientRequestItem, Order
from orders.services import (
    OrderError,
    add_to_client_request,
    change_order_status,
    create_order_from_cart,
    get_draft_request,
    review_client_request,
    submit_client_request,
)
from warehouse.services import StockError


def staff_required(user):
    return user.is_authenticated and user.is_staff


def get_cart(user) -> Cart:
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


@login_required
@require_POST
def cart_add(request, pk):
    if request.user.is_staff:
        messages.info(request, 'Администратор оформляет заказы через админку.')
        return redirect('catalog:product_list')
    product = get_object_or_404(Product, pk=pk, is_active=True)
    form = AddToCartForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Некорректное количество.')
        return redirect(product.get_absolute_url())

    qty = form.cleaned_data['quantity']
    stock = getattr(product, 'stock', None)
    available = stock.quantity_available if stock else 0
    cart = get_cart(request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={'quantity': 0})
    new_qty = (0 if created else item.quantity) + qty
    if new_qty > available:
        messages.error(
            request,
            f'Недостаточно товара «{product.sku}». Доступно: {available} шт.',
        )
        return redirect(product.get_absolute_url())
    item.quantity = new_qty
    item.save()
    messages.success(request, f'«{product.display_name}» добавлен в корзину.')
    return redirect('orders:cart')


@login_required
@require_POST
def cart_update(request, pk):
    cart = get_cart(request.user)
    item = get_object_or_404(CartItem, cart=cart, pk=pk)
    action = request.POST.get('action')
    if action == 'inc':
        qty = item.quantity + 1
    elif action == 'dec':
        qty = item.quantity - 1
    else:
        try:
            qty = int(request.POST.get('quantity', item.quantity))
        except (TypeError, ValueError):
            qty = item.quantity
    if qty <= 0:
        item.delete()
        messages.info(request, 'Позиция удалена из корзины.')
    else:
        available = item.product.stock.quantity_available if hasattr(item.product, 'stock') else 0
        if qty > available:
            messages.error(request, f'Доступно только {available} шт.')
        else:
            item.quantity = qty
            item.save()
    return redirect('orders:cart')


@login_required
@require_POST
def cart_remove(request, pk):
    cart = get_cart(request.user)
    item = get_object_or_404(CartItem, cart=cart, pk=pk)
    item.delete()
    messages.info(request, 'Позиция удалена.')
    return redirect('orders:cart')


@login_required
def cart_detail(request):
    if request.user.is_staff:
        return redirect('orders:active_orders')
    cart = get_cart(request.user)
    items = cart.items.select_related('product', 'product__stock')
    return render(request, 'orders/cart.html', {'cart': cart, 'items': items})


class CheckoutView(LoginRequiredMixin, FormView):
    template_name = 'orders/checkout.html'
    form_class = CheckoutForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff:
            return redirect('orders:active_orders')
        self.cart = get_cart(request.user)
        if not self.cart.items.exists():
            messages.warning(request, 'Корзина пуста.')
            return redirect('orders:cart')
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        user = self.request.user
        return {
            'customer_name': user.get_full_name() or user.username,
            'phone': user.phone,
            'delivery_method': Order.DeliveryMethod.PICKUP,
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cart'] = self.cart
        ctx['items'] = self.cart.items.select_related('product')
        return ctx

    def form_valid(self, form):
        try:
            order = create_order_from_cart(
                user=self.request.user,
                cart=self.cart,
                form_data=form.cleaned_data,
            )
        except (OrderError, StockError) as exc:
            messages.error(self.request, str(exc))
            return redirect('orders:checkout')
        messages.success(
            self.request,
            f'Заказ {order.number} оформлен. Мы свяжемся с вами для согласования перевода.',
        )
        return redirect('orders:order_detail', pk=order.pk)


class OrderListView(LoginRequiredMixin, ListView):
    template_name = 'orders/order_list.html'
    context_object_name = 'orders'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff:
            return redirect('orders:active_orders')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).prefetch_related('items')


class OrderDetailView(LoginRequiredMixin, DetailView):
    template_name = 'orders/order_detail.html'
    context_object_name = 'order'

    def get_queryset(self):
        if self.request.user.is_staff:
            return Order.objects.prefetch_related('items__product', 'status_history')
        return Order.objects.filter(customer=self.request.user).prefetch_related(
            'items__product',
            'status_history',
        )


class ActiveOrdersView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'orders/active_orders.html'
    context_object_name = 'orders'

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        return (
            Order.objects.exclude(
                status__in=[Order.Status.SHIPPED, Order.Status.CANCELLED],
            )
            .select_related('customer')
            .prefetch_related('items__product')
            .order_by('-created_at')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        status_labels = dict(Order.Status.choices)
        for order in ctx['orders']:
            next_statuses = []
            for code in sorted(
                Order.ALLOWED_TRANSITIONS.get(order.status, set()),
                key=lambda s: list(Order.Status.values).index(s),
            ):
                next_statuses.append({'code': code, 'label': status_labels[code]})
            order.next_actions = next_statuses
        return ctx


@login_required
@user_passes_test(staff_required)
@require_POST
def active_order_set_status(request, pk):
    order = get_object_or_404(Order, pk=pk)
    new_status = request.POST.get('status', '')
    try:
        change_order_status(order, new_status, user=request.user)
        messages.success(
            request,
            f'Заказ {order.number}: статус «{order.get_status_display()}».',
        )
    except OrderError as exc:
        messages.error(request, str(exc))
    return redirect('orders:active_orders')


@login_required
@require_POST
def client_request_add(request, pk):
    if request.user.is_staff:
        messages.info(request, 'Администратор оформляет заявки через админку.')
        return redirect('catalog:product_list')
    product = get_object_or_404(Product, pk=pk, is_active=True)
    form = AddToCartForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Некорректное количество.')
        return redirect(product.get_absolute_url())
    try:
        add_to_client_request(
            user=request.user,
            product=product,
            quantity=form.cleaned_data['quantity'],
        )
    except OrderError as exc:
        messages.error(request, str(exc))
        return redirect(product.get_absolute_url())
    messages.success(request, f'«{product.display_name}» добавлен в заявку.')
    return redirect('orders:client_request_draft')


@login_required
def client_request_draft(request):
    if request.user.is_staff:
        return redirect('orders:client_request_inbox')
    draft = get_draft_request(request.user)
    items = draft.items.select_related('product', 'product__stock')
    if request.method == 'POST':
        draft.comment = request.POST.get('comment', '').strip()
        draft.save(update_fields=['comment'])
        try:
            submit_client_request(draft)
        except OrderError as exc:
            messages.error(request, str(exc))
            return redirect('orders:client_request_draft')
        messages.success(request, f'Заявка {draft.number} отправлена.')
        return redirect('orders:client_request_detail', pk=draft.pk)
    return render(request, 'orders/client_request_draft.html', {
        'client_request': draft,
        'items': items,
    })


@login_required
@require_POST
def client_request_update_item(request, pk):
    draft = get_draft_request(request.user)
    item = get_object_or_404(ClientRequestItem, pk=pk, request=draft)
    action = request.POST.get('action')
    if action == 'inc':
        qty = item.quantity + 1
    elif action == 'dec':
        qty = item.quantity - 1
    else:
        try:
            qty = int(request.POST.get('quantity', item.quantity))
        except (TypeError, ValueError):
            qty = item.quantity
    if qty <= 0:
        item.delete()
        messages.info(request, 'Позиция удалена из заявки.')
    else:
        item.quantity = qty
        item.save(update_fields=['quantity'])
    return redirect('orders:client_request_draft')


@login_required
@require_POST
def client_request_remove_item(request, pk):
    draft = get_draft_request(request.user)
    item = get_object_or_404(ClientRequestItem, pk=pk, request=draft)
    item.delete()
    messages.info(request, 'Позиция удалена.')
    return redirect('orders:client_request_draft')


class ClientRequestListView(LoginRequiredMixin, ListView):
    template_name = 'orders/client_request_list.html'
    context_object_name = 'requests'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff:
            return redirect('orders:client_request_inbox')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return (
            ClientRequest.objects.filter(customer=self.request.user)
            .exclude(status=ClientRequest.Status.DRAFT)
            .prefetch_related('items__product')
        )


class ClientRequestDetailView(LoginRequiredMixin, DetailView):
    template_name = 'orders/client_request_detail.html'
    context_object_name = 'client_request'

    def get_queryset(self):
        qs = ClientRequest.objects.prefetch_related('items__product')
        if self.request.user.is_staff:
            return qs
        return qs.filter(customer=self.request.user)


class ClientRequestInboxView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'orders/client_request_inbox.html'
    context_object_name = 'requests'

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        status = self.request.GET.get('status', ClientRequest.Status.SUBMITTED)
        qs = (
            ClientRequest.objects.exclude(status=ClientRequest.Status.DRAFT)
            .select_related('customer', 'reviewed_by')
            .prefetch_related('items__product')
            .order_by('-submitted_at', '-created_at')
        )
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status'] = self.request.GET.get('status', ClientRequest.Status.SUBMITTED)
        ctx['status_choices'] = [
            choice for choice in ClientRequest.Status.choices
            if choice[0] != ClientRequest.Status.DRAFT
        ]
        return ctx


@login_required
@user_passes_test(staff_required)
@require_POST
def client_request_review(request, pk):
    client_request = get_object_or_404(ClientRequest, pk=pk)
    accept = request.POST.get('decision') == 'accept'
    try:
        review_client_request(
            client_request,
            accept=accept,
            user=request.user,
            comment=request.POST.get('review_comment', ''),
        )
        messages.success(
            request,
            f'Заявка {client_request.number}: «{client_request.get_status_display()}».',
        )
    except OrderError as exc:
        messages.error(request, str(exc))
    return redirect('orders:client_request_inbox')
