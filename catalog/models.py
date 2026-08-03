from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from .utils import normalize_code


class Category(models.Model):
    name = models.CharField('Наименование', max_length=200)
    slug = models.SlugField('Slug', max_length=220, unique=True)
    parent = models.ForeignKey(
        'self',
        verbose_name='Родительская категория',
        null=True,
        blank=True,
        related_name='children',
        on_delete=models.CASCADE,
    )
    sort_order = models.PositiveIntegerField('Сортировка', default=0)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name, allow_unicode=True) or 'category'
            slug = base
            i = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{i}'
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_descendant_ids(self):
        ids = [self.pk]
        for child in self.children.all():
            ids.extend(child.get_descendant_ids())
        return ids


class CarMake(models.Model):
    name = models.CharField('Марка', max_length=100, unique=True)
    slug = models.SlugField('Slug', max_length=120, unique=True)

    class Meta:
        verbose_name = 'Марка авто'
        verbose_name_plural = 'Марки авто'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True) or 'make'
        super().save(*args, **kwargs)


class CarModel(models.Model):
    make = models.ForeignKey(
        CarMake,
        verbose_name='Марка',
        related_name='models',
        on_delete=models.CASCADE,
    )
    name = models.CharField('Модель', max_length=100)
    slug = models.SlugField('Slug', max_length=120)

    class Meta:
        verbose_name = 'Модель авто'
        verbose_name_plural = 'Модели авто'
        ordering = ['make__name', 'name']
        unique_together = [('make', 'slug')]

    def __str__(self):
        return f'{self.make.name} {self.name}'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True) or 'model'
        super().save(*args, **kwargs)


class Product(models.Model):
    class Condition(models.TextChoices):
        NEW = 'new', 'Новый'
        USED = 'used', 'Б/У'

    sku = models.CharField('Артикул', max_length=100, unique=True)
    sku_normalized = models.CharField(
        'Артикул (нормализованный)',
        max_length=100,
        db_index=True,
        editable=False,
        blank=True,
    )
    name_ru = models.CharField('Наименование (рус)', max_length=255)
    name_en = models.CharField('Наименование (англ)', max_length=255, blank=True)
    category = models.ForeignKey(
        Category,
        verbose_name='Категория',
        related_name='products',
        on_delete=models.PROTECT,
    )
    condition = models.CharField(
        'Состояние',
        max_length=10,
        choices=Condition.choices,
        default=Condition.NEW,
    )
    price_rub = models.DecimalField('Цена продажи, ₽', max_digits=12, decimal_places=2)
    price_krw = models.DecimalField(
        'Цена продажи, ₩',
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    description_ru = models.TextField('Описание (рус)', blank=True)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.sku} — {self.name_ru}'

    def save(self, *args, **kwargs):
        self.sku_normalized = normalize_code(self.sku)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('catalog:product_detail', kwargs={'pk': self.pk})

    @property
    def unit(self):
        return 'шт'


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        verbose_name='Товар',
        related_name='images',
        on_delete=models.CASCADE,
    )
    image = models.ImageField('Изображение', upload_to='products/%Y/%m/')
    sort_order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Изображение товара'
        verbose_name_plural = 'Изображения товаров'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.product.sku} #{self.sort_order}'


class ProductCrossNumber(models.Model):
    product = models.ForeignKey(
        Product,
        verbose_name='Товар',
        related_name='cross_numbers',
        on_delete=models.CASCADE,
    )
    number = models.CharField('Кросс-номер', max_length=100)
    number_normalized = models.CharField(
        'Нормализованный',
        max_length=100,
        db_index=True,
        editable=False,
        blank=True,
    )
    comment = models.CharField('Комментарий', max_length=200, blank=True)

    class Meta:
        verbose_name = 'Кросс-номер'
        verbose_name_plural = 'Кросс-номера'
        unique_together = [('product', 'number_normalized')]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        self.number_normalized = normalize_code(self.number)
        super().save(*args, **kwargs)


class ProductVehicle(models.Model):
    product = models.ForeignKey(
        Product,
        verbose_name='Товар',
        related_name='vehicles',
        on_delete=models.CASCADE,
    )
    make = models.ForeignKey(CarMake, verbose_name='Марка', on_delete=models.CASCADE)
    model = models.ForeignKey(CarModel, verbose_name='Модель', on_delete=models.CASCADE)
    year_from = models.PositiveIntegerField('Год с', null=True, blank=True)
    year_to = models.PositiveIntegerField('Год по', null=True, blank=True)

    class Meta:
        verbose_name = 'Применимость'
        verbose_name_plural = 'Применимость'
        unique_together = [('product', 'make', 'model', 'year_from', 'year_to')]

    def __str__(self):
        years = ''
        if self.year_from or self.year_to:
            years = f' ({self.year_from or "…"}–{self.year_to or "…"})'
        return f'{self.make} {self.model}{years}'
