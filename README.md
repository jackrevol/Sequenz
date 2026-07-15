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

## Docker image

Build the application image:

```bash
docker build -t sequenz:latest .
```

For a local container smoke test, copy the example environment and replace the secret:

```bash
cp .env.example .env
docker compose up --build
```

The web application is exposed on `http://localhost:8000`, SQLite and uploaded media are persisted in the `sequenz_data` volume, and the `payment-expirer` service releases stock reserved by expired unpaid orders every minute.

The example disables HTTPS-only options so it can run on localhost. In a real deployment, terminate TLS at a reverse proxy and set:

```bash
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
DJANGO_SERVE_MEDIA_FILES=false
```

When `DJANGO_SERVE_MEDIA_FILES=false`, serve `/media/` from object storage or a reverse proxy backed by the persistent media volume. The container health endpoint is `/healthz/`.

## EC2 deployment

`update_sequenz.sh` pulls the ECR image and performs a blue/green deployment. On the
server, place the production `.env` file in the directory where the script is run,
then configure the Nginx Proxy Manager Proxy Host as follows:

```text
Forward Hostname / IP: sequenz-active
Forward Port:          8000
```

Deploy the latest image pushed from `main`:

```bash
./update_sequenz.sh
```

To deploy an immutable image created for a specific Git commit, pass its SHA tag:

```bash
./update_sequenz.sh --tag <git-sha>
```

The defaults assume the shared Docker network is `navi`, the Nginx Proxy Manager
container is `ec2-user-nginx-proxy-manager-1`, and the persistent data volume is
`sequenz_data`. Override them when the server uses different names:

```bash
NETWORK=proxy-network \
NPM_CONTAINER=nginx-proxy-manager \
DATA_VOLUME=sequenz_data \
ENV_FILE=/opt/sequenz/.env \
./update_sequenz.sh
```

The deployment also replaces the `sequenz-payment-expirer` background worker.
Set `DEPLOY_WORKER=false` only when that job is managed separately.
If the production `DJANGO_ALLOWED_HOSTS` does not include `localhost`, set
`HEALTH_HOST_HEADER` to one of its configured hostnames when running the script.

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
export SABANGNET_CLIENT_ID="b3e3cdb2-de0e-4fd8-99c2-e9ad995c5401"
export SABANGNET_CLIENT_SECRET='$2a$10$gQrOTxi6PvteD6SShn0Fk.'
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
