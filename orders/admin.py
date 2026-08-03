from django.contrib import admin, messages
from django.utils.html import format_html

from orders.services import OrderError, change_order_status

from .models import Cart, CartItem, Order, OrderItem, OrderStatusHistory


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ('product',)
    readonly_fields = ('price_rub',)


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ('previous_status', 'new_status', 'changed_at', 'user')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'number',
        'colored_status',
        'customer',
        'customer_name',
        'phone',
        'delivery_method',
        'created_at',
        'total_display',
    )
    list_filter = ('status', 'delivery_method', 'messenger')
    search_fields = ('number', 'customer_name', 'phone', 'customer__email', 'customer__username')
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    readonly_fields = ('number', 'created_at', 'status_changed_at')
    actions = [
        'action_confirm',
        'action_assemble',
        'action_ship',
        'action_cancel',
    ]
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    @admin.display(description='Статус')
    def colored_status(self, obj):
        colors = {
            Order.Status.NEW: '#0d6efd',
            Order.Status.CONFIRMED: '#198754',
            Order.Status.ASSEMBLED: '#fd7e14',
            Order.Status.SHIPPED: '#6c757d',
            Order.Status.CANCELLED: '#dc3545',
        }
        return format_html(
            '<span style="color:{};font-weight:700;">{}</span>',
            colors.get(obj.status, '#000'),
            obj.get_status_display(),
        )

    @admin.display(description='Сумма, ₽')
    def total_display(self, obj):
        return obj.total_rub

    def _bulk_status(self, request, queryset, status):
        ok, fail = 0, 0
        for order in queryset:
            try:
                change_order_status(order, status, user=request.user)
                ok += 1
            except OrderError as exc:
                fail += 1
                self.message_user(request, f'{order}: {exc}', level=messages.ERROR)
        if ok:
            self.message_user(request, f'Обновлено заказов: {ok}', level=messages.SUCCESS)
        if fail:
            self.message_user(request, f'Ошибок: {fail}', level=messages.WARNING)

    @admin.action(description='→ Подтвержден')
    def action_confirm(self, request, queryset):
        self._bulk_status(request, queryset, Order.Status.CONFIRMED)

    @admin.action(description='→ Собран')
    def action_assemble(self, request, queryset):
        self._bulk_status(request, queryset, Order.Status.ASSEMBLED)

    @admin.action(description='→ Отправлен')
    def action_ship(self, request, queryset):
        self._bulk_status(request, queryset, Order.Status.SHIPPED)

    @admin.action(description='→ Отменен')
    def action_cancel(self, request, queryset):
        self._bulk_status(request, queryset, Order.Status.CANCELLED)


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'updated_at')
    inlines = [CartItemInline]
