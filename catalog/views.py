from django.conf import settings
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from .models import CarMake, CarModel, Category, Product
from .services import filter_products


class ProductListView(ListView):
    model = Product
    template_name = 'catalog/product_list.html'
    context_object_name = 'products'
    paginate_by = settings.PRODUCTS_PER_PAGE

    def get_queryset(self):
        category = None
        category_slug = self.request.GET.get('category')
        if category_slug:
            category = Category.objects.filter(slug=category_slug).first()

        return filter_products(
            q=self.request.GET.get('q', '').strip(),
            category=category,
            condition=self.request.GET.get('condition', ''),
            make_id=self.request.GET.get('make') or None,
            model_id=self.request.GET.get('model') or None,
            in_stock=self.request.GET.get('in_stock') == '1',
            sort=self.request.GET.get('sort', '-created_at'),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = Category.objects.filter(parent__isnull=True).prefetch_related('children')
        ctx['makes'] = CarMake.objects.all()
        make_id = self.request.GET.get('make')
        ctx['models'] = CarModel.objects.filter(make_id=make_id) if make_id else CarModel.objects.none()
        ctx['filters'] = {
            'q': self.request.GET.get('q', ''),
            'category': self.request.GET.get('category', ''),
            'condition': self.request.GET.get('condition', ''),
            'make': self.request.GET.get('make', ''),
            'model': self.request.GET.get('model', ''),
            'in_stock': self.request.GET.get('in_stock', ''),
            'sort': self.request.GET.get('sort', '-created_at'),
        }
        return ctx


class ProductDetailView(DetailView):
    model = Product
    template_name = 'catalog/product_detail.html'
    context_object_name = 'product'

    def get_queryset(self):
        return Product.objects.filter(is_active=True).select_related(
            'category', 'stock'
        ).prefetch_related('images', 'cross_numbers', 'vehicles__make', 'vehicles__model')
