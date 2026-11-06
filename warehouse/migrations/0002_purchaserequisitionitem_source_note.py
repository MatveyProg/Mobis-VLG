from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('warehouse', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaserequisitionitem',
            name='source_note',
            field=models.TextField(
                blank=True,
                help_text='Кто сколько заказал и сколько ушло в расход',
                verbose_name='Состав количества',
            ),
        ),
    ]
