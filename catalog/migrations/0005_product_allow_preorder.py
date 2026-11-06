from django.db import migrations, models
from django.utils.text import slugify

from catalog.utils import normalize_code

DEFAULT_VEHICLE_SPECS = (
    ('Hyundai', 'ix55 239 л.с.'),
    ('Hyundai', 'ix55 250 л.с.'),
    ('Hyundai', 'ix55 264 л.с.'),
    ('Hyundai', 'Veracruz 239 л.с.'),
)


def fill_defaults(apps, schema_editor):
    Product = apps.get_model('catalog', 'Product')
    ProductCrossNumber = apps.get_model('catalog', 'ProductCrossNumber')
    ProductVehicle = apps.get_model('catalog', 'ProductVehicle')
    CarMake = apps.get_model('catalog', 'CarMake')
    CarModel = apps.get_model('catalog', 'CarModel')

    models_cache = []
    for make_name, model_name in DEFAULT_VEHICLE_SPECS:
        make, _ = CarMake.objects.get_or_create(
            name=make_name,
            defaults={'slug': slugify(make_name, allow_unicode=True) or 'make'},
        )
        model, _ = CarModel.objects.get_or_create(
            make=make,
            name=model_name,
            defaults={'slug': slugify(model_name, allow_unicode=True) or 'model'},
        )
        models_cache.append((make, model))

    for product in Product.objects.all():
        sku_norm = normalize_code(product.sku)
        parts = [product.sku, sku_norm, product.name_ru, product.name_en, product.description_ru]
        for cross in ProductCrossNumber.objects.filter(product=product):
            parts.append(cross.number)
            parts.append(cross.number_normalized)
        product.sku_normalized = sku_norm
        product.search_text = ' '.join(part for part in parts if part).casefold()
        product.save(update_fields=['sku_normalized', 'search_text'])

        if not ProductVehicle.objects.filter(product=product).exists():
            for make, model in models_cache:
                ProductVehicle.objects.get_or_create(
                    product=product,
                    make=make,
                    model=model,
                    year_from=None,
                    year_to=None,
                )


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0004_product_search_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='allow_preorder',
            field=models.BooleanField(
                default=True,
                verbose_name='Возможность заказывать при нулевом остатке',
            ),
        ),
        migrations.RunPython(fill_defaults, migrations.RunPython.noop),
    ]
