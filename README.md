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

## Production settings

Production fails fast when the secret key is missing. Configure at least:

```bash
export DJANGO_ENV=production
export DJANGO_SECRET_KEY="a-long-random-production-secret"
export DJANGO_ALLOWED_HOSTS="shop.example.com"
export PAYMENT_PENDING_TIMEOUT_MINUTES=30
```

Run `.venv/bin/python manage.py check --deploy` with the production environment before deployment.

## Initial APIs

- `GET /api/catalog/listings/`
- `GET /api/catalog/listings/<id>/`
- `GET /api/commerce/cart/items/` with `X-Guest-Key`
- `POST /api/commerce/cart/items/` with `X-Guest-Key`
- `POST /api/commerce/orders/` with `X-Guest-Key`

## Sabangnet synchronization

Configure credentials and the response item names enabled for the connected Sabangnet account:

```bash
export SABANGNET_API_BASE_URL="https://..."
export SABANGNET_BEARER_TOKEN="..."
export SABANGNET_SVC_ACCOUNT_ID="..."
export SABANGNET_ORDER_STATUS_MAP='{"actual_status_code":"delivered"}'
export SABANGNET_ORDER_SHIPMENT_RESPONSE_ITEMS='["WAYBILL_NO","DELIVERY_COMPANY_CODE","DELIVERY_COMPANY_NAME"]'
```

Synchronize recent order, delivery, and tracking data:

```bash
.venv/bin/python manage.py sync_sabangnet_order_statuses --start-date 2026-07-01 --end-date 2026-07-12
```

Run this command every 5–10 minutes with the deployment platform's scheduler. Unknown external status codes are stored without changing the internal fulfillment status.

Expire unpaid orders and release locally reserved stock every minute:

```bash
.venv/bin/python manage.py expire_payment_pending_orders
```

Product availability is calculated as Sabangnet stock minus local reservations. After manually registering an exported workbook in Sabangnet, use the `Sabangnet order exports` admin action to mark it registered. The action first reloads the order products from Sabangnet and only releases the local reservation after every product sync succeeds.
