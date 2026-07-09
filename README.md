# Sequenz

Mobile-first clothing commerce backend built with Django and Django REST Framework.

## Local Development

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

## Tests

```bash
.venv/bin/python -m pytest -q
.venv/bin/python manage.py check
```

## Initial APIs

- `GET /api/catalog/listings/`
- `GET /api/catalog/listings/<id>/`
- `GET /api/commerce/cart/items/` with `X-Guest-Key`
- `POST /api/commerce/cart/items/` with `X-Guest-Key`
- `POST /api/commerce/orders/` with `X-Guest-Key`
