from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from catalog.forms import ProductImportForm
from catalog.import_products import import_products_from_xlsx

from .models import (
    CarMake,
    CarModel,
    Category,
    Product,
    ProductCrossNumber,
    ProductImage,
    ProductVehicle,
)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductCrossNumberInline(admin.TabularInline):
    model = ProductCrossNumber
    extra = 1


class ProductVehicleInline(admin.TabularInline):
    model = ProductVehicle
    extra = 1
    autocomplete_fields = ('make', 'model')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'sort_order', 'slug')
    list_editable = ('sort_order',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(CarMake)
class CarMakeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(CarModel)
class CarModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'make', 'slug')
    list_filter = ('make',)
    search_fields = ('name', 'make__name')
    autocomplete_fields = ('make',)
    prepopulated_fields = {'slug': ('name',)}


class StockAvailableFilter(admin.SimpleListFilter):
    title = 'наличие'
    parameter_name = 'availability'

    def lookups(self, request, model_admin):
        return (
            ('in_stock', 'В наличии'),
            ('out', 'Нет в наличии'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'in_stock':
            return queryset.filter(stock__quantity_on_hand__gt=0)
        if self.value() == 'out':
            return queryset.filter(stock__quantity_on_hand=0)
        return queryset


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'sku',
        'name_ru',
        'category',
        'condition',
        'price_rub',
        'purchase_price_krw',
        'purchase_price_rub',
        'weight',
        'quantity_in_car',
        'stock_available',
        'allow_preorder',
        'is_active',
    )
    list_filter = ('is_active', 'allow_preorder', 'condition', 'category', StockAvailableFilter)
    search_fields = ('sku', 'name_ru', 'name_en', 'sku_normalized', 'search_text', 'cross_numbers__number')
    inlines = [ProductImageInline, ProductCrossNumberInline, ProductVehicleInline]
    autocomplete_fields = ('category',)
    readonly_fields = ('sku_normalized', 'created_at')
    fieldsets = (
        (None, {
            'fields': (
                'sku', 'name_ru', 'name_en', 'category', 'condition',
                'allow_preorder', 'is_active',
            ),
        }),
        ('Цены', {
            'fields': (
                'price_rub',
                ('purchase_price_krw', 'purchase_price_rub'),
            ),
        }),
        ('Характеристики', {
            'fields': ('weight', 'quantity_in_car', 'description_ru'),
        }),
        ('Служебные', {
            'fields': ('sku_normalized', 'created_at'),
            'classes': ('collapse',),
        }),
    )
    change_list_template = 'admin/catalog/product/change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'import-xlsx/',
                self.admin_site.admin_view(self.import_xlsx_view),
                name='catalog_product_import_xlsx',
            ),
        ]
        return custom + urls

    def import_xlsx_view(self, request):
        form = ProductImportForm(request.POST or None, request.FILES or None)
        if request.method == 'POST' and form.is_valid():
            try:
                result = import_products_from_xlsx(form.cleaned_data['file'])
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect('admin:catalog_product_import_xlsx')

            msg = (
                f'Импорт завершён: создано {result["created"]}, '
                f'обновлено {result["updated"]}, пропущено {result["skipped"]}.'
            )
            if result['errors']:
                messages.warning(request, msg)
                for err in result['errors'][:20]:
                    messages.error(request, err)
                if len(result['errors']) > 20:
                    messages.error(request, f'…и ещё {len(result["errors"]) - 20} ошибок.')
            else:
                messages.success(request, msg)
            return redirect('admin:catalog_product_changelist')

        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'title': 'Импорт товаров из Excel',
            'opts': self.model._meta,
            'expected_columns': [
                '1. Артикул', '2. Кросс-номер', '3. Количество в машине',
                '4. Наименование англ', '5. Наименование на русском',
                '6. Цена продажи', '7. Цена закупки руб', '8. Цена W', '9. Вес',
                '(первая строка — заголовки)',
            ],
        }
        return render(request, 'admin/catalog/product/import_form.html', context)

    @admin.display(description='Доступно')
    def stock_available(self, obj):
        stock = getattr(obj, 'stock', None)
        if not stock:
            return 0
        color = '#198754' if stock.quantity_available > 0 else '#dc3545'
        return format_html(
            '<span style="color:{}; font-weight:600;">{}</span> '
            '<span style="color:#6c757d;">(склад {}, резерв {})</span>',
            color,
            stock.quantity_available,
            stock.quantity_on_hand,
            stock.quantity_reserved,
        )
