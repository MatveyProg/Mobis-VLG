from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Category, Product
from orders.models import ClientRequest
from orders.services import add_to_client_request, review_client_request, submit_client_request
from warehouse.models import Stock


class ClientRequestFlowTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Оптика', slug='optika')
        self.product = Product.objects.create(
            sku='111111',
            name_ru='Фара',
            category=self.category,
            price_rub=1000,
            allow_preorder=True,
        )
        Stock.objects.filter(product=self.product).update(quantity_on_hand=0, quantity_reserved=0)
        self.customer = User.objects.create_user('client', password='pass1234', first_name='Иван')
        self.admin = User.objects.create_user('boss', password='pass1234', is_staff=True, is_superuser=True)

    def test_add_submit_accept(self):
        self.product.refresh_from_db()
        request = add_to_client_request(user=self.customer, product=self.product, quantity=2)
        self.assertEqual(request.status, ClientRequest.Status.DRAFT)
        submit_client_request(request)
        request.refresh_from_db()
        self.assertEqual(request.status, ClientRequest.Status.SUBMITTED)
        review_client_request(request, accept=True, user=self.admin)
        request.refresh_from_db()
        self.assertEqual(request.status, ClientRequest.Status.ACCEPTED)

    def test_order_button_on_detail(self):
        self.client.login(username='client', password='pass1234')
        response = self.client.get(self.product.get_absolute_url())
        self.assertContains(response, 'Заказать')
        self.assertContains(response, reverse('orders:client_request_add', args=[self.product.pk]))
