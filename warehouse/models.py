from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from catalog.models import Product


class Supplier(models.Model):
    name = models.CharField('Наименование', max_length=255)
    contact_person = models.CharField('Контактное лицо', max_length=200, blank=True)
    phone = models.CharField('Телефон', max_length=64, blank=True)
    email = models.EmailField('Email', blank=True)
    address = models.TextField('Адрес', blank=True)

    class Meta:
        verbose_name = 'Поставщик'
        verbose_name_plural = 'Поставщики'
        ordering = ['name']

    def __str__(self):
        return self.name


class Stock(models.Model):
    product = models.OneToOneField(
        Product,
        verbose_name='Товар',
        related_name='stock',
        on_delete=models.CASCADE,
    )
    quantity_on_hand = models.PositiveIntegerField('На складе', default=0)
    quantity_reserved = models.PositiveIntegerField('В резерве', default=0)

    class Meta:
        verbose_name = 'Остаток'
        verbose_name_plural = 'Остатки'

    def __str__(self):
        return f'{self.product.sku}: {self.quantity_available} доступно'

    @property
    def quantity_available(self):
        return max(self.quantity_on_hand - self.quantity_reserved, 0)

    def clean(self):
        if self.quantity_reserved > self.quantity_on_hand:
            raise ValidationError('Резерв не может превышать остаток на складе.')


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        IN = 'IN', 'Приход'
        OUT = 'OUT', 'Расход'
        RESERVE = 'RESERVE', 'Резерв'
        UNRESERVE = 'UNRESERVE', 'Снятие резерва'
        STORNO_OUT = 'STORNO_OUT', 'Сторно расхода'

    product = models.ForeignKey(
        Product,
        verbose_name='Товар',
        related_name='movements',
        on_delete=models.PROTECT,
    )
    movement_type = models.CharField('Тип', max_length=20, choices=MovementType.choices)
    quantity = models.PositiveIntegerField('Количество')
    created_at = models.DateTimeField('Дата', default=timezone.now)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Пользователь',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    comment = models.CharField('Комментарий', max_length=255, blank=True)
    order = models.ForeignKey(
        'orders.Order',
        verbose_name='Заказ',
        null=True,
        blank=True,
        related_name='stock_movements',
        on_delete=models.SET_NULL,
    )
    stock_in = models.ForeignKey(
        'StockIn',
        verbose_name='Приход',
        null=True,
        blank=True,
        related_name='stock_movements',
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = 'Движение склада'
        verbose_name_plural = 'Движения склада'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.movement_type} {self.product.sku} × {self.quantity}'


class StockIn(models.Model):
    supplier = models.ForeignKey(
        Supplier,
        verbose_name='Поставщик',
        related_name='stock_ins',
        on_delete=models.PROTECT,
    )
    date = models.DateTimeField('Дата', default=timezone.now)
    is_posted = models.BooleanField('Проведён', default=False)
    requisition = models.ForeignKey(
        'PurchaseRequisition',
        verbose_name='Заявка на закупку',
        null=True,
        blank=True,
        related_name='stock_ins',
        on_delete=models.SET_NULL,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Создал',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Приход'
        verbose_name_plural = 'Приходы'
        ordering = ['-date']

    def __str__(self):
        status = 'проведён' if self.is_posted else 'черновик'
        return f'Приход #{self.pk} ({status})'


class StockInItem(models.Model):
    stock_in = models.ForeignKey(
        StockIn,
        verbose_name='Приход',
        related_name='items',
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(Product, verbose_name='Товар', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField('Количество')
    purchase_price_rub = models.DecimalField(
        'Цена закупки, ₽',
        max_digits=12,
        decimal_places=2,
    )
    requisition_item = models.ForeignKey(
        'PurchaseRequisitionItem',
        verbose_name='Строка заявки',
        null=True,
        blank=True,
        related_name='stock_in_items',
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = 'Строка прихода'
        verbose_name_plural = 'Строки прихода'

    def __str__(self):
        return f'{self.product.sku} × {self.quantity}'


class PurchaseRequisition(models.Model):
    class Status(models.TextChoices):
        CREATED = 'created', 'Создана'
        IN_PROGRESS = 'in_progress', 'В работе'
        RECEIVED = 'received', 'Получено'
        # v2 placeholders (not used in UI yet):
        # MOBIS / TK / IN_TRANSIT / RECEIVED_RF

    number = models.CharField('Номер', max_length=32, unique=True, blank=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=Status.choices,
        default=Status.CREATED,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Создатель',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    note = models.TextField('Комментарий', blank=True)

    class Meta:
        verbose_name = 'Заявка на закупку'
        verbose_name_plural = 'Заявки на закупку'
        ordering = ['-created_at']

    def __str__(self):
        return self.number or f'Заявка #{self.pk}'

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.number:
            year = timezone.localdate().year
            seq = PurchaseRequisition.objects.filter(number__startswith=f'ЗК-{year}-').count() + 1
            self.number = f'ЗК-{year}-{seq:04d}'
            super().save(update_fields=['number'])


class PurchaseRequisitionItem(models.Model):
    requisition = models.ForeignKey(
        PurchaseRequisition,
        verbose_name='Заявка',
        related_name='items',
        on_delete=models.CASCADE,
    )
    line_number = models.PositiveIntegerField('№ п/п', default=1)
    product = models.ForeignKey(Product, verbose_name='Товар', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField('Количество')
    purchase_price_krw = models.DecimalField(
        'Цена закупки, ₩',
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    purchase_price_rub = models.DecimalField(
        'Цена закупки, ₽',
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    class Meta:
        verbose_name = 'Строка заявки'
        verbose_name_plural = 'Строки заявки'
        ordering = ['line_number', 'id']

    def __str__(self):
        return f'{self.product.sku} × {self.quantity}'

    @property
    def sum_krw(self):
        return self.quantity * self.purchase_price_krw

    @property
    def sum_rub(self):
        return self.quantity * self.purchase_price_rub

    @property
    def quantity_received(self):
        total = self.stock_in_items.filter(
            stock_in__is_posted=True,
        ).aggregate(s=Sum('quantity'))['s']
        return total or 0

    @property
    def quantity_remaining(self):
        return max(self.quantity - self.quantity_received, 0)


class PurchaseRequisitionStatusHistory(models.Model):
    requisition = models.ForeignKey(
        PurchaseRequisition,
        related_name='status_history',
        on_delete=models.CASCADE,
    )
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = 'История статуса заявки'
        verbose_name_plural = 'История статусов заявок'
        ordering = ['-changed_at']
