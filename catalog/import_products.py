"""Import products from Excel (.xlsx). First row = headers (skipped as data).

Standard column order (1-based):
1 артикул, 2 кросс-номер, 3 количество в машине, 4 наименование англ,
5 наименование на русском, 6 цена продажи, 7 цена закупки руб, 8 цена W, 9 вес.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from catalog.models import Category, Product, ProductCrossNumber
from catalog.utils import normalize_code

DEFAULT_CATEGORY = 'Импорт'

STANDARD_FIELDS = (
    'sku',
    'cross_number',
    'quantity_in_car',
    'name_en',
    'name_ru',
    'price_rub',
    'purchase_price_rub',
    'purchase_price_krw',
    'weight',
)


def _norm_header(value: Any) -> str:
    if value is None:
        return ''
    text = str(value).strip().lower()
    text = text.replace('₩', 'w').replace('₽', 'rub').replace('won', 'w')
    text = re.sub(r'\s+', ' ', text)
    return text


HEADER_MAP = {
    'sku': {
        'артикул', 'sku', 'номенклатурный номер', 'номер детали', 'part number',
    },
    'cross_number': {
        'кросс-номер', 'кросс номер', 'кросс', 'cross', 'cross number',
        'кросс номер', 'ое', 'oe', 'oem',
    },
    'name_ru': {
        'наименование (рус)', 'наименование рус', 'название (рус)', 'name ru',
        'русское название', 'russian name', 'наименование на русском',
        'наименование русское',
    },
    'name_en': {
        'наименование (англ)', 'наименование англ', 'наименование eng',
        'название (англ)', 'name en', 'english name', 'part name',
        'наименование английское',
    },
    'category': {'категория', 'category', 'группа'},
    'condition': {'состояние', 'condition'},
    'price_rub': {
        'цена продажи', 'цена продажи руб', 'цена продажи, rub',
        'продажа руб', 'цена',
    },
    'purchase_price_krw': {
        'цена закупки w', 'цена закупки вон', 'цена w',
        'закупка w', 'цена закупки, w', 'цена w',
    },
    'purchase_price_rub': {
        'цена закупки руб', 'закупка руб', 'цена закупки, rub',
        'цена закупки rub',
    },
    'weight': {'вес', 'weight', 'вес кг', 'вес, кг'},
    'quantity_in_car': {
        'количество в машине', 'кол-во в машине', 'кол во в машине', 'qty in car',
        'кол-во',
    },
    'description_ru': {'описание (рус)', 'описание'},
}

_CYRILLIC_RE = re.compile(r'[а-яё]', re.IGNORECASE)
_LATIN_RE = re.compile(r'[a-z]', re.IGNORECASE)


def looks_english(text: str) -> bool:
    if not text:
        return False
    return bool(_LATIN_RE.search(text)) and not bool(_CYRILLIC_RE.search(text))


def _name_lang_hint(header: str) -> str | None:
    if any(token in header for token in ('англ', 'eng', 'english')):
        return 'name_en'
    if any(token in header for token in ('рус', 'russian')):
        return 'name_ru'
    if header in {'name', 'наименование', 'название'}:
        return None
    return None


def _is_standard_layout(headers: list[Any]) -> bool:
    """Fixed 9-column shop template: артикул | кросс | кол-во в машине | англ | рус | ..."""
    if len(headers) < 9:
        return False
    first = _norm_header(headers[0])
    second = _norm_header(headers[1])
    sku_ok = 'артикул' in first or first in {'sku', 'part number'}
    if not sku_ok:
        return False
    cross_ok = 'кросс' in second or 'cross' in second or second == ''
    return bool(cross_ok or True)


def _build_column_index(headers: list[Any]) -> dict[str, int]:
    if _is_standard_layout(headers):
        mapping = {field: idx for idx, field in enumerate(STANDARD_FIELDS)}
        extra = _build_header_mapping(headers, skip_indices=set(range(9)))
        extra.update(mapping)
        return extra

    mapping = _build_header_mapping(headers)
    if 'sku' not in mapping:
        raise ValueError(
            'Не найден столбец «Артикул». Проверьте заголовки первой строки файла.'
        )
    return mapping


def _build_header_mapping(headers: list[Any], skip_indices: set[int] | None = None) -> dict[str, int]:
    mapping: dict[str, int] = {}
    used_cols: set[int] = set(skip_indices or ())
    normalized = [_norm_header(h) for h in headers]

    for idx, header in enumerate(normalized):
        if idx in used_cols:
            continue
        hinted = _name_lang_hint(header)
        if hinted and hinted not in mapping:
            mapping[hinted] = idx
            used_cols.add(idx)

    candidates: list[tuple[int, str, int]] = []
    for field, aliases in HEADER_MAP.items():
        for idx, header in enumerate(normalized):
            if not header or idx in used_cols or field in mapping:
                continue
            if header in aliases:
                candidates.append((1000 + len(header), field, idx))
                continue
            for alias in sorted(aliases, key=len, reverse=True):
                if len(alias) < 5:
                    continue
                if alias in header:
                    candidates.append((len(alias), field, idx))
                    break

    for _score, field, idx in sorted(candidates, reverse=True):
        if field in mapping or idx in used_cols:
            continue
        mapping[field] = idx
        used_cols.add(idx)

    if 'name_ru' not in mapping and 'name_en' not in mapping:
        for idx, header in enumerate(normalized):
            if idx in used_cols:
                continue
            if header in {'наименование', 'название', 'name', 'part name'}:
                mapping['name_generic'] = idx
                break

    return mapping


def _cell(row: tuple, idx: int | None):
    if idx is None or idx >= len(row):
        return None
    return row[idx]


def _to_decimal(value) -> Decimal:
    if value is None or value == '':
        return Decimal('0')
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    text = str(value).strip().replace(' ', '').replace(',', '.')
    if not text:
        return Decimal('0')
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f'Некорректное число: {value}') from exc


def _to_int(value, default=0) -> int:
    if value is None or value == '':
        return default
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return default
    return int(float(text.replace(',', '.')))


def _parse_condition(value) -> str:
    if not value:
        return Product.Condition.NEW
    text = str(value).strip().lower()
    if text in ('б/у', 'б.у.', 'used', 'б у', 'bu'):
        return Product.Condition.USED
    return Product.Condition.NEW


def _get_or_create_category(name: str | None) -> Category:
    title = (name or '').strip() or DEFAULT_CATEGORY
    category, _ = Category.objects.get_or_create(
        name=title,
        defaults={'slug': ''},
    )
    return category


def _split_cross_numbers(value) -> list[str]:
    if value is None or value == '':
        return []
    text = str(value).strip()
    if not text:
        return []
    parts = re.split(r'[,;/|]+', text)
    seen = set()
    result = []
    for part in parts:
        number = part.strip()
        if not number:
            continue
        key = normalize_code(number)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(number)
    return result


def _sync_cross_numbers(product: Product, numbers: list[str]) -> None:
    existing = {
        item.number_normalized: item
        for item in product.cross_numbers.all()
    }
    for number in numbers:
        norm = normalize_code(number)
        current = existing.pop(norm, None)
        if current is None:
            ProductCrossNumber.objects.create(product=product, number=number)
        elif current.number != number:
            current.number = number
            current.save(update_fields=['number', 'number_normalized'])
    product.save()


@transaction.atomic
def import_products_from_xlsx(file_obj) -> dict[str, Any]:
    from openpyxl import load_workbook

    wb = load_workbook(file_obj, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError('Файл пустой.')

    col = _build_column_index(list(rows[0]))
    created = updated = skipped = 0
    errors: list[str] = []

    for line_no, row in enumerate(rows[1:], start=2):
        if not row or all(v is None or str(v).strip() == '' for v in row):
            skipped += 1
            continue
        sku_raw = _cell(row, col.get('sku'))
        if not sku_raw:
            skipped += 1
            continue
        sku = str(sku_raw).strip()
        try:
            category = _get_or_create_category(_cell(row, col.get('category')))
            name_ru = str(_cell(row, col.get('name_ru')) or '').strip()
            name_en = str(_cell(row, col.get('name_en')) or '').strip()
            if not name_ru and not name_en:
                generic = str(_cell(row, col.get('name_generic')) or '').strip()
                if looks_english(generic):
                    name_en = generic
                else:
                    name_ru = generic
            elif name_ru and not name_en and looks_english(name_ru):
                name_en = name_ru
                name_ru = ''
            defaults = {
                'name_ru': name_ru,
                'name_en': name_en,
                'category': category,
                'condition': _parse_condition(_cell(row, col.get('condition'))),
                'price_rub': _to_decimal(_cell(row, col.get('price_rub'))),
                'purchase_price_krw': _to_decimal(_cell(row, col.get('purchase_price_krw'))),
                'purchase_price_rub': _to_decimal(_cell(row, col.get('purchase_price_rub'))),
                'description_ru': str(_cell(row, col.get('description_ru')) or '').strip(),
                'is_active': True,
            }
            weight_val = _cell(row, col.get('weight'))
            if weight_val not in (None, ''):
                defaults['weight'] = _to_decimal(weight_val)
            if col.get('quantity_in_car') is not None:
                qty_in_car = _to_int(_cell(row, col.get('quantity_in_car')), default=1)
                defaults['quantity_in_car'] = max(qty_in_car, 1)

            product, was_created = Product.objects.update_or_create(
                sku=sku,
                defaults=defaults,
            )
            _sync_cross_numbers(product, _split_cross_numbers(_cell(row, col.get('cross_number'))))
            if was_created:
                created += 1
            else:
                updated += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f'Строка {line_no} ({sku}): {exc}')

    wb.close()
    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'errors': errors,
    }
