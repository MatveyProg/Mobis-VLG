from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from catalog.models import Category, Product
from orders.models import ClientRequest, ClientRequestItem, Order, OrderItem
from warehouse.models import PurchaseRequisition, PurchaseRequisitionItem
from warehouse.requisition import build_requisition_from_sales, renumber_requisition_items


class RequisitionBuildTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Оптика', slug='optika')
        self.product = Product.objects.create(
            sku='111111',
            name_ru='Фара',
            category=self.category,
            price_rub=1000,
            purchase_price_rub=500,
            purchase_price_krw=10000,
        )
        self.kolya = User.objects.create_user('kolya', password='pass1234', first_name='Коля')
        self.vasya = User.objects.create_user('vasya', password='pass1234', first_name='Вася')
        self.admin = User.objects.create_user('admin', password='pass1234', is_staff=True)

    def test_groups_sales_and_accepted_requests_by_sku(self):
        now = timezone.now()
        order = Order.objects.create(
            customer=self.kolya,
            customer_name='Коля',
            phone='1',
            messenger=Order.Messenger.TELEGRAM,
            messenger_contact='k',
            delivery_method=Order.DeliveryMethod.PICKUP,
            status=Order.Status.CONFIRMED,
        )
        Order.objects.filter(pk=order.pk).update(status_changed_at=now)
        OrderItem.objects.create(order=order, product=self.product, quantity=2, price_rub=1000)

        req_k = ClientRequest.objects.create(
            customer=self.kolya,
            status=ClientRequest.Status.ACCEPTED,
        )
        ClientRequestItem.objects.create(
            request=req_k, product=self.product, quantity=2, price_rub=1000,
        )
        req_v = ClientRequest.objects.create(
            customer=self.vasya,
            status=ClientRequest.Status.ACCEPTED,
        )
        ClientRequestItem.objects.create(
            request=req_v, product=self.product, quantity=1, price_rub=1000,
        )

        requisition = build_requisition_from_sales(
            date_from=(now - timedelta(days=1)).date(),
            date_to=(now + timedelta(days=1)).date(),
            user=self.admin,
        )
        items = list(requisition.items.all())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].quantity, 5)
        self.assertIn('продажи: 2 шт', items[0].source_note)
        self.assertIn('Коля: 2 шт', items[0].source_note)
        self.assertIn('Вася: 1 шт', items[0].source_note)

    def test_delete_item_renumbers_and_totals(self):
        req = PurchaseRequisition.objects.create(created_by=self.admin)
        other = Product.objects.create(
            sku='222222', name_ru='Фонарь', category=self.category, price_rub=100,
            purchase_price_rub=Decimal('10'),
        )
        PurchaseRequisitionItem.objects.create(
            requisition=req, line_number=1, product=self.product, quantity=2,
            purchase_price_rub=Decimal('100'),
        )
        second = PurchaseRequisitionItem.objects.create(
            requisition=req, line_number=2, product=other, quantity=3,
            purchase_price_rub=Decimal('20'),
        )
        first = req.items.get(line_number=1)
        first.delete()
        renumber_requisition_items(req)
        remaining = req.items.get()
        self.assertEqual(remaining.pk, second.pk)
        self.assertEqual(remaining.line_number, 1)
        self.assertEqual(remaining.sum_rub, Decimal('60'))
