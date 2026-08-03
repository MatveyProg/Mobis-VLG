from django.contrib import admin, messages
from django.utils.html import format_html

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
        'price_krw',
        'stock_available',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active', 'condition', 'category', StockAvailableFilter)
    search_fields = ('sku', 'name_ru', 'name_en', 'sku_normalized', 'cross_numbers__number')
    inlines = [ProductImageInline, ProductCrossNumberInline, ProductVehicleInline]
    autocomplete_fields = ('category',)
    readonly_fields = ('sku_normalized', 'created_at')

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
