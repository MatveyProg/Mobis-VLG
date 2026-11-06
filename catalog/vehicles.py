from catalog.models import CarMake, CarModel, ProductVehicle

DEFAULT_VEHICLE_SPECS = (
    ('Hyundai', 'ix55 239 л.с.'),
    ('Hyundai', 'ix55 250 л.с.'),
    ('Hyundai', 'ix55 264 л.с.'),
    ('Hyundai', 'Veracruz 239 л.с.'),
)


def get_or_create_default_car_models():
    models = []
    for make_name, model_name in DEFAULT_VEHICLE_SPECS:
        make, _ = CarMake.objects.get_or_create(name=make_name, defaults={'slug': ''})
        model, _ = CarModel.objects.get_or_create(
            make=make,
            name=model_name,
            defaults={'slug': ''},
        )
        models.append((make, model))
    return models


def apply_default_vehicles(product, *, force=False):
    """Assign the four default cars when the product has no applicability."""
    if product.pk is None:
        return
    if not force and product.vehicles.exists():
        return
    for make, model in get_or_create_default_car_models():
        ProductVehicle.objects.get_or_create(
            product=product,
            make=make,
            model=model,
            year_from=None,
            year_to=None,
        )
