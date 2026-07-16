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
are loaded from AWS Systems Manager Parameter Store under `/sequenz/prod`.
Configure the Nginx Proxy Manager Proxy Host as follows:

```text
Forward Hostname / IP: sequenz-active
Forward Port:          8000
```

Deploy the latest image pushed from `main`:

```bash
./update_sequenz.sh
```

Parameter names use `/sequenz/{prod|dev}/{keyname}`. No parameter is required
merely to start the server. Add the following sets only when each integration is
enabled:

| Integration | Key name | Type | Required when |
| --- | --- | --- | --- |
| Toss Payments | `TOSS_CLIENT_KEY` | `SecureString` | Opening the payment widget |
| Toss Payments | `TOSS_SECRET_KEY` | `SecureString` | Confirming, looking up, or cancelling payments |
| Sabangnet | `SABANGNET_CLIENT_ID` | `SecureString` | Using Sabangnet OAuth/API |
| Sabangnet | `SABANGNET_CLIENT_SECRET` | `SecureString` | Using Sabangnet OAuth/API |
| Sabangnet | `SABANGNET_SVC_ACCOUNT_ID` | `SecureString` | Calling Sabangnet business APIs |
| Sabangnet | `SABANGNET_AUTH_MODE` | `SecureString` | Set to `SANDBOX` under `dev`; `prod` defaults to `PRODUCTION` |
| Sabangnet status sync | `SABANGNET_ORDER_STATUS_MAP` | `SecureString` (JSON object) | Mapping external statuses to internal statuses |
| Sabangnet shipment sync | `SABANGNET_ORDER_SHIPMENT_RESPONSE_ITEMS` | `SecureString` (JSON array) | Requesting tracking/carrier fields enabled for the account |

For example, a production Toss setup consists of:

```text
/sequenz/prod/TOSS_CLIENT_KEY
/sequenz/prod/TOSS_SECRET_KEY
```

A development Sabangnet setup consists of:

```text
/sequenz/dev/SABANGNET_CLIENT_ID
/sequenz/dev/SABANGNET_CLIENT_SECRET
/sequenz/dev/SABANGNET_SVC_ACCOUNT_ID
/sequenz/dev/SABANGNET_AUTH_MODE = SANDBOX
```

Optional Sabangnet synchronization value examples:

```text
/sequenz/prod/SABANGNET_ORDER_STATUS_MAP = {"external_status_code":"shipped"}
/sequenz/prod/SABANGNET_ORDER_SHIPMENT_RESPONSE_ITEMS = ["WAYBILL_NO","LOGISTICS_CD","LOGISTICS_NM"]
```

Replace `external_status_code` only after confirming the real status code. Allowed
internal status values are `pending`, `preparing`, `ready_to_ship`, `shipped`,
`in_transit`, `delivered`, `cancelled`, and `returned`.

All parameters under these paths must use `SecureString`; the deployment script
warns and ignores `String` and `StringList` parameters. The EC2 role should allow
`ssm:GetParametersByPath` and, for a customer-managed KMS key, `kms:Decrypt`.
Missing parameters, empty values, access denial, and lookup failures only produce
a warning; deployment continues with empty integration credentials. Storefront
pages and `/healthz/` therefore remain available. Use a different path or disable
the lookup explicitly when needed:

```bash
./update_sequenz.sh -d
./update_sequenz.sh --skip-ssm
```

`-d` (or `--dev`) selects `/sequenz/dev` and isolates the deployment as
`sequenz-dev-blue/green`, `sequenz-dev-active`, and the `sequenz_dev_data` volume.
It uses the same ECR image as production. Configure the development NPM Proxy Host
to forward to `sequenz-dev-active:8000`.

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
/sequenz/prod/SABANGNET_CLIENT_ID
/sequenz/prod/SABANGNET_CLIENT_SECRET
/sequenz/prod/SABANGNET_SVC_ACCOUNT_ID
```

Production is the default. For a sandbox deployment, also set
`/sequenz/dev/SABANGNET_AUTH_MODE` to `SANDBOX`.

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
