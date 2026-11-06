import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0005_product_allow_preorder'),
        ('warehouse', '0002_purchaserequisitionitem_source_note'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='stockmovement',
            name='movement_type',
            field=models.CharField(
                choices=[
                    ('IN', 'Приход'),
                    ('OUT', 'Расход'),
                    ('RESERVE', 'Резерв'),
                    ('UNRESERVE', 'Снятие резерва'),
                    ('STORNO_IN', 'Сторно прихода'),
                    ('STORNO_OUT', 'Сторно расхода'),
                ],
                max_length=20,
                verbose_name='Тип',
            ),
        ),
        migrations.CreateModel(
            name='StockOut',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Дата')),
                ('is_posted', models.BooleanField(default=False, verbose_name='Проведён')),
                ('note', models.CharField(blank=True, max_length=255, verbose_name='Комментарий')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Создал',
                )),
            ],
            options={
                'verbose_name': 'Расход',
                'verbose_name_plural': 'Расходы',
                'ordering': ['-date'],
            },
        ),
        migrations.CreateModel(
            name='StockOutItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(verbose_name='Количество')),
                ('price_rub', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Цена, ₽')),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to='catalog.product',
                    verbose_name='Товар',
                )),
                ('stock_out', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                    to='warehouse.stockout',
                    verbose_name='Расход',
                )),
            ],
            options={
                'verbose_name': 'Строка расхода',
                'verbose_name_plural': 'Строки расхода',
            },
        ),
        migrations.AddField(
            model_name='stockmovement',
            name='stock_out',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='stock_movements',
                to='warehouse.stockout',
                verbose_name='Расход',
            ),
        ),
    ]
