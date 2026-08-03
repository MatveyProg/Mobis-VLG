from django.db.models import F, Prefetch, Q

from catalog.models import Product
from catalog.utils import normalize_code


def filter_products(queryset=None, *, q='', category=None, condition='', make_id=None,
                    model_id=None, in_stock=False, sort='-created_at'):
    qs = queryset if queryset is not None else Product.objects.filter(is_active=True)
    qs = qs.select_related('category', 'stock').prefetch_related(
        'images',
        'cross_numbers',
        Prefetch('vehicles'),
    )

    if q:
        norm = normalize_code(q)
        qs = qs.filter(
            Q(name_ru__icontains=q)
            | Q(name_en__icontains=q)
            | Q(sku__icontains=q)
            | Q(sku_normalized__icontains=norm)
            | Q(cross_numbers__number__icontains=q)
            | Q(cross_numbers__number_normalized__icontains=norm)
        ).distinct()

    if category is not None:
        qs = qs.filter(category_id__in=category.get_descendant_ids())

    if condition:
        qs = qs.filter(condition=condition)

    if make_id:
        qs = qs.filter(vehicles__make_id=make_id)
    if model_id:
        qs = qs.filter(vehicles__model_id=model_id)
    if make_id or model_id:
        qs = qs.distinct()

    if in_stock:
        qs = qs.filter(stock__quantity_on_hand__gt=F('stock__quantity_reserved'))

    allowed_sorts = {
        'price': 'price_rub',
        '-price': '-price_rub',
        'created': 'created_at',
        '-created': '-created_at',
        '-created_at': '-created_at',
        'created_at': 'created_at',
    }
    qs = qs.order_by(allowed_sorts.get(sort, '-created_at'))
    return qs
