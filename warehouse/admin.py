from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from warehouse.models import (
    PurchaseRequisition,
    PurchaseRequisitionItem,
    PurchaseRequisitionStatusHistory,
    Stock,
    StockIn,
    StockInItem,
    StockMovement,
    Supplier,
)
from warehouse.requisition import build_requisition_from_sales
from warehouse.services import StockError, post_stock_in


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone', 'email')
    search_fields = ('name', 'contact_person', 'phone', 'email')


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = (
        'product',
        'quantity_on_hand',
        'quantity_reserved',
        'available',
    )
    search_fields = ('product__sku', 'product__name_ru')
    readonly_fields = ('product', 'quantity_on_hand', 'quantity_reserved')

    @admin.display(description='Доступно')
    def available(self, obj):
        return obj.quantity_available

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'movement_type', 'product', 'quantity', 'user', 'comment')
    list_filter = ('movement_type',)
    search_fields = ('product__sku', 'comment')
    readonly_fields = (
        'product',
        'movement_type',
        'quantity',
        'created_at',
        'user',
        'comment',
        'order',
        'stock_in',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class StockInItemInline(admin.TabularInline):
    model = StockInItem
    extra = 1
    autocomplete_fields = ('product', 'requisition_item')


@admin.register(StockIn)
class StockInAdmin(admin.ModelAdmin):
    list_display = ('id', 'date', 'supplier', 'is_posted', 'requisition', 'post_button')
    list_filter = ('is_posted', 'supplier')
    inlines = [StockInItemInline]
    autocomplete_fields = ('supplier', 'requisition')
    readonly_fields = ('is_posted', 'created_at', 'created_by')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description='Действие')
    def post_button(self, obj):
        if obj.is_posted or not obj.pk:
            return '—' if not obj.is_posted else 'Проведён'
        url = reverse('admin:warehouse_stockin_post', args=[obj.pk])
        return format_html('<a class="button" href="{}">Провести</a>', url)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<int:pk>/post/',
                self.admin_site.admin_view(self.post_view),
                name='warehouse_stockin_post',
            ),
        ]
        return custom + urls

    def post_view(self, request, pk):
        stock_in = StockIn.objects.get(pk=pk)
        try:
            post_stock_in(stock_in, user=request.user)
            self.message_user(request, f'Приход #{pk} проведён.', messages.SUCCESS)
        except StockError as exc:
            self.message_user(request, str(exc), messages.ERROR)
        return redirect('admin:warehouse_stockin_change', pk)


class PurchaseRequisitionItemInline(admin.TabularInline):
    model = PurchaseRequisitionItem
    extra = 1
    autocomplete_fields = ('product',)
    readonly_fields = ('received_display', 'remaining_display')
    fields = (
        'line_number',
        'product',
        'quantity',
        'purchase_price_krw',
        'purchase_price_rub',
        'received_display',
        'remaining_display',
    )

    @admin.display(description='Оприходовано')
    def received_display(self, obj):
        if not obj.pk:
            return '—'
        return obj.quantity_received

    @admin.display(description='Осталось')
    def remaining_display(self, obj):
        if not obj.pk:
            return '—'
        return obj.quantity_remaining


class PurchaseRequisitionStatusHistoryInline(admin.TabularInline):
    model = PurchaseRequisitionStatusHistory
    extra = 0
    readonly_fields = ('previous_status', 'new_status', 'changed_at', 'user')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PurchaseRequisition)
class PurchaseRequisitionAdmin(admin.ModelAdmin):
    list_display = ('number', 'status', 'created_at', 'created_by')
    list_filter = ('status',)
    search_fields = ('number',)
    inlines = [PurchaseRequisitionItemInline, PurchaseRequisitionStatusHistoryInline]
    readonly_fields = ('number', 'created_at')
    actions = ['to_in_progress', 'to_received']
    change_list_template = 'admin/warehouse/purchaserequisition/change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'from-sales/',
                self.admin_site.admin_view(self.from_sales_view),
                name='warehouse_purchaserequisition_from_sales',
            ),
        ]
        return custom + urls

    def from_sales_view(self, request):
        if request.method == 'POST':
            date_from = request.POST.get('date_from')
            date_to = request.POST.get('date_to')
            try:
                from datetime import date
                d1 = date.fromisoformat(date_from)
                d2 = date.fromisoformat(date_to)
                req = build_requisition_from_sales(date_from=d1, date_to=d2, user=request.user)
                self.message_user(
                    request,
                    f'Создана заявка {req.number} ({req.items.count()} позиций).',
                    messages.SUCCESS,
                )
                return redirect('admin:warehouse_purchaserequisition_change', req.pk)
            except Exception as exc:  # noqa: BLE001
                self.message_user(request, str(exc), messages.ERROR)
        return render(request, 'admin/warehouse/purchaserequisition/from_sales.html', {
            'title': 'Заявка по расходу',
            'opts': self.model._meta,
        })

    def save_model(self, request, obj, form, change):
        creating = obj.pk is None
        old_status = None
        if not creating:
            old_status = PurchaseRequisition.objects.filter(pk=obj.pk).values_list(
                'status', flat=True
            ).first()
        if creating:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        if creating or (old_status and old_status != obj.status):
            PurchaseRequisitionStatusHistory.objects.create(
                requisition=obj,
                previous_status=old_status or '',
                new_status=obj.status,
                user=request.user,
            )

    def _set_status(self, request, queryset, status):
        for obj in queryset:
            if obj.status == status:
                continue
            old = obj.status
            obj.status = status
            obj.save(update_fields=['status'])
            PurchaseRequisitionStatusHistory.objects.create(
                requisition=obj,
                previous_status=old,
                new_status=status,
                user=request.user,
            )
        self.message_user(request, 'Статусы обновлены.', messages.SUCCESS)

    @admin.action(description='→ В работе')
    def to_in_progress(self, request, queryset):
        self._set_status(request, queryset, PurchaseRequisition.Status.IN_PROGRESS)

    @admin.action(description='→ Получено')
    def to_received(self, request, queryset):
        self._set_status(request, queryset, PurchaseRequisition.Status.RECEIVED)


@admin.register(PurchaseRequisitionItem)
class PurchaseRequisitionItemAdmin(admin.ModelAdmin):
    list_display = ('requisition', 'line_number', 'product', 'quantity')
    search_fields = ('product__sku', 'requisition__number')
    autocomplete_fields = ('product', 'requisition')
