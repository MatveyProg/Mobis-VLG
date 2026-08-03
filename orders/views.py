from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, FormView, ListView

from catalog.models import Product
from orders.forms import AddToCartForm, CheckoutForm
from orders.models import Cart, CartItem, Order
from orders.services import OrderError, change_order_status, create_order_from_cart
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
    messages.success(request, f'«{product.name_ru}» добавлен в корзину.')
    return redirect('orders:cart')


@login_required
@require_POST
def cart_update(request, pk):
    cart = get_cart(request.user)
    item = get_object_or_404(CartItem, cart=cart, pk=pk)
    try:
        qty = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        qty = 1
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
            messages.success(request, 'Корзина обновлена.')
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
