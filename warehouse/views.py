from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render

from catalog.models import Product


def staff_required(user):
    return user.is_authenticated and user.is_staff


@login_required
@user_passes_test(staff_required)
def stock_balances(request):
    products = (
        Product.objects.select_related('stock', 'category')
        .order_by('sku')
    )
    q = request.GET.get('q', '').strip()
    if q:
        from catalog.utils import normalize_code
        from django.db.models import Q
        norm = normalize_code(q)
        products = products.filter(
            Q(sku__icontains=q)
            | Q(sku_normalized__icontains=norm)
            | Q(name_ru__icontains=q)
        )
    only_positive = request.GET.get('positive') == '1'
    rows = []
    for p in products:
        stock = getattr(p, 'stock', None)
        on_hand = stock.quantity_on_hand if stock else 0
        reserved = stock.quantity_reserved if stock else 0
        available = stock.quantity_available if stock else 0
        if only_positive and on_hand <= 0:
            continue
        rows.append({
            'product': p,
            'on_hand': on_hand,
            'reserved': reserved,
            'available': available,
        })
    return render(request, 'warehouse/stock_balances.html', {
        'rows': rows,
        'q': q,
        'positive': only_positive,
    })
