from django.conf import settings
from django.db import models
from django.utils import timezone

from catalog.models import Product


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'Новый'
        CONFIRMED = 'confirmed', 'Подтвержден'
        ASSEMBLED = 'assembled', 'Собран'
        SHIPPED = 'shipped', 'Отправлен'
        CANCELLED = 'cancelled', 'Отменен'

    class DeliveryMethod(models.TextChoices):
        PICKUP = 'pickup', 'Самовывоз'
        DELIVERY = 'delivery', 'Доставка'

    class Messenger(models.TextChoices):
        TELEGRAM = 'telegram', 'Telegram'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        MAX = 'max', 'Max'
        IMO = 'imo', 'Imo'
        OTHER = 'other', 'Прочее'

    ALLOWED_TRANSITIONS = {
        Status.NEW: {Status.CONFIRMED, Status.CANCELLED},
        Status.CONFIRMED: {Status.ASSEMBLED, Status.CANCELLED},
        Status.ASSEMBLED: {Status.SHIPPED, Status.CANCELLED},
        Status.SHIPPED: set(),
        Status.CANCELLED: set(),
    }

    number = models.CharField('Номер', max_length=32, unique=True, blank=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Клиент',
        related_name='orders',
        on_delete=models.PROTECT,
    )
    customer_name = models.CharField('Имя', max_length=200)
    phone = models.CharField('Телефон', max_length=64)
    messenger = models.CharField(
        'Мессенджер',
        max_length=20,
        choices=Messenger.choices,
    )
    messenger_contact = models.CharField('Контакт в мессенджере', max_length=200)
    delivery_method = models.CharField(
        'Способ получения',
        max_length=20,
        choices=DeliveryMethod.choices,
    )
    delivery_address = models.TextField('Адрес доставки', blank=True)
    comment = models.TextField('Комментарий', blank=True)
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    status_changed_at = models.DateTimeField('Статус изменён', auto_now_add=True)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']

    def __str__(self):
        return self.number or f'Заказ #{self.pk}'

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.number:
            year = timezone.localdate().year
            seq = Order.objects.filter(number__startswith=f'З-{year}-').count() + 1
            self.number = f'З-{year}-{seq:04d}'
            super().save(update_fields=['number'])

    @property
    def total_rub(self):
        return sum((item.line_total for item in self.items.all()), start=0)


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        verbose_name='Заказ',
        related_name='items',
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        verbose_name='Товар',
        on_delete=models.PROTECT,
    )
    quantity = models.PositiveIntegerField('Количество')
    price_rub = models.DecimalField(
        'Цена на момент заказа, ₽',
        max_digits=12,
        decimal_places=2,
    )

    class Meta:
        verbose_name = 'Строка заказа'
        verbose_name_plural = 'Строки заказа'

    def __str__(self):
        return f'{self.product.sku} × {self.quantity}'

    @property
    def line_total(self):
        return self.quantity * self.price_rub


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(
        Order,
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
        verbose_name = 'История статуса заказа'
        verbose_name_plural = 'История статусов заказов'
        ordering = ['-changed_at']


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name='cart',
        on_delete=models.CASCADE,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'

    def __str__(self):
        return f'Корзина {self.user}'

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def total_rub(self):
        return sum((item.line_total for item in self.items.select_related('product')), start=0)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Позиция корзины'
        verbose_name_plural = 'Позиции корзины'
        unique_together = [('cart', 'product')]

    @property
    def line_total(self):
        return self.quantity * self.product.price_rub
