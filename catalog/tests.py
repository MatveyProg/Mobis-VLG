from decimal import Decimal
from io import BytesIO

from django.test import TestCase
from openpyxl import Workbook

from catalog.import_products import import_products_from_xlsx
from catalog.models import Category, Product, ProductCrossNumber
from catalog.services import filter_products


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class ProductImportAndSearchTests(TestCase):
    def test_import_standard_nine_columns(self):
        file_obj = _xlsx([
            [
                'Артикул', 'Кросс-номер', 'Количество в машине',
                'Наименование англ', 'Наименование на русском',
                'Цена продажи', 'Цена закупки руб', 'Цена W', 'Вес',
            ],
            ['111111', 'OE-999', 2, 'Head lamp', 'Фара', 1500, 900, 18000, 1.25],
        ])
        result = import_products_from_xlsx(file_obj)
        self.assertEqual(result['created'], 1)
        self.assertEqual(result['errors'], [])
        product = Product.objects.get(sku='111111')
        self.assertEqual(product.name_en, 'Head lamp')
        self.assertEqual(product.name_ru, 'Фара')
        self.assertEqual(product.quantity_in_car, 2)
        self.assertEqual(product.price_rub, Decimal('1500'))
        self.assertEqual(product.purchase_price_rub, Decimal('900'))
        self.assertEqual(product.purchase_price_krw, Decimal('18000'))
        self.assertEqual(product.weight, Decimal('1.25'))
        self.assertTrue(product.allow_preorder)
        self.assertTrue(product.cross_numbers.filter(number='OE-999').exists())
        self.assertEqual(product.vehicles.count(), 4)

    def test_search_all_fields_case_insensitive(self):
        category = Category.objects.create(name='Свет', slug='svet')
        product = Product.objects.create(
            sku='ABC-1',
            name_ru='Фара передняя',
            name_en='Front Lamp',
            category=category,
            price_rub=100,
            description_ru='Для Hyundai ix55',
        )
        ProductCrossNumber.objects.create(product=product, number='OE-777')
        product.refresh_from_db()
        for query in ('фара', 'FRONT', 'abc-1', 'oe-777', 'hyundai'):
            qs = filter_products(q=query)
            self.assertIn(product, list(qs), msg=query)
