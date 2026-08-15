"""Import products from Excel (.xlsx). First row = headers (skipped as data)."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from catalog.models import Category, Product
from catalog.utils import normalize_code

DEFAULT_CATEGORY = 'Импорт'


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
    'name_ru': {
        'наименование (рус)', 'наименование рус', 'название (рус)', 'name ru',
        'русское название', 'russian name',
    },
    'name_en': {
        'наименование (англ)', 'наименование англ', 'наименование eng',
        'название (англ)', 'name en', 'english name', 'part name',
    },
    'category': {'категория', 'category', 'группа'},
    'condition': {'состояние', 'condition'},
    'price_rub': {
        'цена продажи', 'цена продажи руб', 'цена продажи, rub',
        'продажа руб',
    },
    'purchase_price_krw': {
        'цена закупки w', 'цена закупки вон', 'цена w',
        'закупка w', 'цена закупки, w',
    },
    'purchase_price_rub': {
        'цена закупки руб', 'закупка руб', 'цена закупки, rub',
    },
    'weight': {'вес', 'weight', 'вес кг', 'вес, кг'},
    'quantity_in_car': {
        'количество в машине', 'кол-во в машине', 'кол во в машине', 'qty in car',
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


def _build_column_index(headers: list[Any]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    used_cols: set[int] = set()
    normalized = [_norm_header(h) for h in headers]

    for idx, header in enumerate(normalized):
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

    # Generic single "Наименование" / "Name" column, if language not specified.
    if 'name_ru' not in mapping and 'name_en' not in mapping:
        for idx, header in enumerate(normalized):
            if idx in used_cols:
                continue
            if header in {'наименование', 'название', 'name', 'part name'}:
                mapping['name_generic'] = idx
                break

    if 'sku' not in mapping:
        raise ValueError(
            'Не найден столбец «Артикул». Проверьте заголовки первой строки файла.'
        )
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
                defaults['quantity_in_car'] = max(
                    _to_int(_cell(row, col.get('quantity_in_car')), default=1),
                    1,
                )

            product, was_created = Product.objects.update_or_create(
                sku=sku,
                defaults=defaults,
            )
            product.sku_normalized = normalize_code(sku)
            product.save(update_fields=['sku_normalized'])
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
