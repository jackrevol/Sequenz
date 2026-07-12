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
