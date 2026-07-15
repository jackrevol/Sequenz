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

The production image has code defaults for the Django signing key and allowed
hosts, so it starts without external configuration. Until the production domain is
fixed, `ALLOWED_HOSTS` defaults to `*`. Narrow it later in `sequenz/settings.py` or
with the optional `DJANGO_ALLOWED_HOSTS` Parameter Store value.

Run `.venv/bin/python manage.py check --deploy` with the production environment
before deployment.

## Docker image

Build the application image:

```bash
docker build -t sequenz:latest .
```

For a local container smoke test:

```bash
docker compose up --build
```

The web application is exposed on `http://localhost:8000`, SQLite and uploaded media are persisted in the `sequenz_data` volume, and the `payment-expirer` service releases stock reserved by expired unpaid orders every minute.

Docker Compose overrides the image to development mode so it can run over HTTP on
localhost. The production image enables HTTPS security settings and expects TLS to
terminate at the reverse proxy. Serve `/media/` from object storage or a reverse
proxy backed by the persistent media volume. The container health endpoint is
`/healthz/`.

## EC2 deployment

`update_sequenz.sh` pulls the ECR image and performs a blue/green deployment. All
startup configuration has code defaults. Optional integration credentials
are loaded from AWS Systems Manager Parameter Store under `/sequenz/production`.
Configure the Nginx Proxy Manager Proxy Host as follows:

```text
Forward Hostname / IP: sequenz-active
Forward Port:          8000
```

Deploy the latest image pushed from `main`:

```bash
./update_sequenz.sh
```

Parameter names must end with the Django environment variable name:

```text
/sequenz/production/TOSS_CLIENT_KEY
/sequenz/production/TOSS_SECRET_KEY
/sequenz/production/SABANGNET_CLIENT_ID
/sequenz/production/SABANGNET_CLIENT_SECRET
/sequenz/production/SABANGNET_SVC_ACCOUNT_ID
```

Use `SecureString` for credentials. The EC2 role should allow
`ssm:GetParametersByPath` and, for a customer-managed KMS key, `kms:Decrypt`.
Missing parameters, empty values, access denial, and lookup failures only produce
a warning; deployment continues with empty integration credentials. Storefront
pages and `/healthz/` therefore remain available. Use a different path or disable
the lookup explicitly when needed:

```bash
SSM_PARAMETER_PATH=/sequenz/staging ./update_sequenz.sh
./update_sequenz.sh --skip-ssm
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

Store these credentials in Parameter Store when the connected Sabangnet account is approved:

```text
/sequenz/production/SABANGNET_CLIENT_ID
/sequenz/production/SABANGNET_CLIENT_SECRET
/sequenz/production/SABANGNET_SVC_ACCOUNT_ID
```

Production is the default. For a sandbox deployment, also set
`/sequenz/staging/SABANGNET_AUTH_MODE` to `SANDBOX`.

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
