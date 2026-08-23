from django.db.models import Count, F
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView

from catalog.models import CarModel, Category, Product
from catalog.services import filter_products

_CATALOG_QUERY_KEYS = {'q', 'category', 'condition', 'make', 'model', 'in_stock', 'sort', 'page'}


class HomeView(TemplateView):
    template_name = 'pages/home.html'

    def get(self, request, *args, **kwargs):
        if _CATALOG_QUERY_KEYS.intersection(request.GET.keys()):
            target = reverse('catalog:product_list')
            qs = request.GET.urlencode()
            return redirect(f'{target}?{qs}' if qs else target)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        categories = list(
            Category.objects.filter(parent__isnull=True)
            .annotate(n_products=Count('products'))
            .order_by('sort_order', 'name')
        )
        ctx['categories'] = categories
        ctx['featured_products'] = list(
            filter_products(in_stock=True, sort='-created_at')[:8]
        )
        ctx['car_models'] = [
            {'id': model.id, 'make_id': model.make_id, 'name': model.name}
            for model in CarModel.objects.select_related('make').order_by('make__name', 'name')
        ]
        ctx['product_count'] = Product.objects.filter(is_active=True).count()
        ctx['in_stock_count'] = Product.objects.filter(
            is_active=True,
            stock__quantity_on_hand__gt=F('stock__quantity_reserved'),
        ).count()
        return ctx


class OfferView(TemplateView):
    template_name = 'pages/offer.html'


class PrivacyView(TemplateView):
    template_name = 'pages/privacy.html'
