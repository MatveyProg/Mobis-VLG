"""Import stock-in lines from Excel.

Column A — SKU, column B — quantity, column C — purchase price RUB.
First row is skipped if it looks like a header.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from warehouse.models import StockIn, StockInItem
from warehouse.utils import get_product_by_sku


def _is_header_row(sku, qty) -> bool:
    sku_text = str(sku or '').strip().lower()
    header_markers = (
        'артикул',
        'номенклатур',
        'sku',
        'номер',
        'товар',
    )
    if any(marker in sku_text for marker in header_markers):
        return True
    try:
        _to_int(qty)
    except (TypeError, ValueError):
        return True
    return False


def _to_int(value) -> int:
    if value is None or value == '':
        raise ValueError('пустое количество')
    if isinstance(value, bool):
        raise ValueError('некорректное количество')
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip().replace(' ', '').replace(',', '.')
    return int(float(text))


def _to_decimal(value) -> Decimal:
    if value is None or value == '':
        raise ValueError('пустая цена')
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    text = str(value).strip().replace(' ', '').replace(',', '.')
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f'некорректная цена: {value}') from exc


@transaction.atomic
def import_stock_in_items_from_xlsx(stock_in: StockIn, file_obj) -> dict[str, Any]:
    from openpyxl import load_workbook

    if stock_in.is_posted:
        raise ValueError('Проведённый приход нельзя изменять.')

    wb = load_workbook(file_obj, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        raise ValueError('Файл пустой.')

    start = 0
    if rows and _is_header_row(rows[0][0] if rows[0] else None, rows[0][1] if len(rows[0]) > 1 else None):
        start = 1

    created = skipped = 0
    errors: list[str] = []

    for line_no, row in enumerate(rows[start:], start=start + 1):
        if not row or all(v is None or str(v).strip() == '' for v in row[:3]):
            skipped += 1
            continue
        sku_raw = row[0] if len(row) > 0 else None
        qty_raw = row[1] if len(row) > 1 else None
        price_raw = row[2] if len(row) > 2 else None
        sku = str(sku_raw).strip() if sku_raw is not None else ''
        if not sku:
            skipped += 1
            continue
        try:
            product = get_product_by_sku(sku)
            quantity = _to_int(qty_raw)
            if quantity <= 0:
                raise ValueError('количество должно быть больше нуля')
            price = _to_decimal(price_raw)
            if price < 0:
                raise ValueError('цена не может быть отрицательной')
            StockInItem.objects.create(
                stock_in=stock_in,
                product=product,
                quantity=quantity,
                purchase_price_rub=price,
            )
            created += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f'Строка {line_no} ({sku or "без артикула"}): {exc}')

    return {
        'created': created,
        'skipped': skipped,
        'errors': errors,
    }
