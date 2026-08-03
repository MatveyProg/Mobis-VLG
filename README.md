# Mobis-VLG

Интернет-магазин автозапчастей: витрина + личный кабинет + складской учёт (Django).

## Стек

- Python 3.12+, Django 5.x
- SQLite (v1), готовность к PostgreSQL через env
- Bootstrap 5, WhiteNoise, openpyxl, Pillow

## Быстрый старт

```bash
python -m venv .venv
.\.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- Витрина: http://127.0.0.1:8000/
- Админка: http://127.0.0.1:8000/admin/
- Отчёты: http://127.0.0.1:8000/reports/

Регистрация клиентов: **email + пароль** (без подтверждения почты). Email используется как логин.

## Операционный цикл админа

1. Завести категории, марки/модели, товары (с кроссами и применимостью).
2. Создать поставщика → документ **Приход** → кнопка **Провести** (увеличит остаток).
3. Клиент оформляет заказ → статус **Новый** (резерв).
4. В админке action **→ Подтвержден** (списание).
5. Далее: Собран → Отправлен. Отмена до «Отправлен» корректно возвращает остаток.
6. **Заявки на закупку**: вручную или «Создать по расходу»; частичный приход — несколько проведённых приходов, связанных с заявкой/строками.

## Бэкапы (Beget)

Регулярно копируйте:

- `db.sqlite3`
- папку `media/`

## Переход на PostgreSQL

В `.env`:

```
DJANGO_DB_ENGINE=django.db.backends.postgresql
DJANGO_DB_NAME=mobis_vlg
DJANGO_DB_USER=...
DJANGO_DB_PASSWORD=...
DJANGO_DB_HOST=localhost
DJANGO_DB_PORT=5432
```

Затем `migrate` на чистой БД (или dump/load данных).

## ТЗ

См. `Tekhnicheskoe_zadanie_v2.md`.
