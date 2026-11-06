import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0005_product_allow_preorder'),
        ('orders', '0001_initial'),
        ('warehouse', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ClientRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(blank=True, max_length=32, unique=True, verbose_name='Номер')),
                ('status', models.CharField(
                    choices=[
                        ('draft', 'Черновик'),
                        ('submitted', 'Отправлена'),
                        ('accepted', 'Принята'),
                        ('rejected', 'Отклонена'),
                    ],
                    default='draft',
                    max_length=20,
                    verbose_name='Статус',
                )),
                ('comment', models.TextField(blank=True, verbose_name='Комментарий')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создана')),
                ('submitted_at', models.DateTimeField(blank=True, null=True, verbose_name='Отправлена')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='Рассмотрена')),
                ('review_comment', models.CharField(blank=True, max_length=255, verbose_name='Комментарий администратора')),
                ('customer', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='client_requests',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Клиент',
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reviewed_client_requests',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Рассмотрел',
                )),
            ],
            options={
                'verbose_name': 'Заявка клиента',
                'verbose_name_plural': 'Заявки клиентов',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ClientRequestItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='Количество')),
                ('price_rub', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Цена на момент заявки, ₽')),
                ('allocated_requisition', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='client_request_items',
                    to='warehouse.purchaserequisition',
                    verbose_name='Включена в заявку на закупку',
                )),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to='catalog.product',
                    verbose_name='Товар',
                )),
                ('request', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                    to='orders.clientrequest',
                    verbose_name='Заявка',
                )),
            ],
            options={
                'verbose_name': 'Строка заявки клиента',
                'verbose_name_plural': 'Строки заявок клиентов',
                'unique_together': {('request', 'product')},
            },
        ),
    ]
