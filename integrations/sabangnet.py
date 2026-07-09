import json
from dataclasses import dataclass, field
from urllib import error, request

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from commerce.models import Order

from .models import SabangnetOrderSubmission


class SabangnetClientError(Exception):
    pass


@dataclass(frozen=True)
class SabangnetResponse:
    sabangnet_order_no: str = ""
    raw_summary: dict = field(default_factory=dict)


class SabangnetClient:
    def __init__(self, base_url=None, order_submit_path=None, bearer_token=None, svc_account_id=None, timeout=10):
        self.base_url = base_url or getattr(settings, "SABANGNET_BASE_URL", "")
        self.order_submit_path = order_submit_path or getattr(settings, "SABANGNET_ORDER_SUBMIT_PATH", "")
        self.bearer_token = bearer_token or getattr(settings, "SABANGNET_BEARER_TOKEN", "")
        self.svc_account_id = svc_account_id or getattr(settings, "SABANGNET_SVC_ACCOUNT_ID", "")
        self.timeout = timeout

    def submit_order(self, payload):
        if not self.base_url or not self.order_submit_path:
            raise SabangnetClientError("Sabangnet order submit endpoint is not configured.")
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = request.Request(
            f"{self.base_url.rstrip('/')}/{self.order_submit_path.lstrip('/')}",
            data=body,
            method="POST",
            headers=self._headers(),
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                response_body = response.read().decode("utf-8")
                data = json.loads(response_body) if response_body else {}
        except error.HTTPError as exc:
            safe_body = exc.read().decode("utf-8", errors="replace")[:500]
            raise SabangnetClientError(f"Sabangnet HTTP {exc.code}: {safe_body}") from exc
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise SabangnetClientError(f"Sabangnet request failed: {exc}") from exc
        return SabangnetResponse(
            sabangnet_order_no=_extract_sabangnet_order_no(data),
            raw_summary=_safe_response_summary(data),
        )

    def _headers(self):
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        if self.svc_account_id:
            headers["X-Svc-Acnt-Id"] = self.svc_account_id
        return headers


def build_order_payload(order):
    items = []
    for item in order.items.order_by("id"):
        items.append(
            {
                "line_no": str(item.id),
                "listing_code": item.listing_code_snapshot,
                "sabangnet_product_code": item.sabangnet_product_code,
                "custom_product_code": item.custom_product_code,
                "barcode": item.barcode_snapshot,
                "product_name": item.product_name_snapshot,
                "option_name": item.option_name_snapshot,
                "quantity": item.ordered_quantity,
                "unit_price": item.unit_price,
                "line_total": item.line_total,
            }
        )
    return {
        "shop_order_no": order.order_number,
        "ordered_at": order.ordered_at.isoformat(),
        "buyer": {
            "name": order.buyer_name,
            "phone": order.buyer_phone,
            "email": order.buyer_email,
        },
        "receiver": {
            "name": order.recipient_name,
            "phone": order.recipient_phone,
            "postal_code": order.postal_code,
            "address1": order.address1,
            "address2": order.address2,
            "delivery_memo": order.delivery_memo,
        },
        "amounts": {
            "items_subtotal": order.items_subtotal,
            "shipping_fee": order.shipping_fee,
            "coupon_discount_amount": order.coupon_discount_amount,
            "point_used_amount": order.point_used_amount,
            "payment_amount": order.payment_amount,
        },
        "items": items,
    }


def submit_order_submission(submission, client):
    with transaction.atomic():
        locked_submission = (
            SabangnetOrderSubmission.objects.select_for_update().select_related("order").get(pk=submission.pk)
        )
        if locked_submission.status == SabangnetOrderSubmission.Status.SENT:
            return locked_submission
        order = locked_submission.order
        if order.status != Order.Status.PAID:
            _mark_submission_failed(locked_submission, "Order is not paid.")
            return locked_submission
        payload = build_order_payload(order)
        locked_submission.attempt_count += 1
        locked_submission.last_attempt_at = timezone.now()
        locked_submission.payload_summary = {
            "order_number": order.order_number,
            "payment_amount": order.payment_amount,
            "item_count": order.items.count(),
        }
        locked_submission.save(
            update_fields=["attempt_count", "last_attempt_at", "payload_summary", "updated_at"]
        )

        try:
            response = client.submit_order(payload)
        except SabangnetClientError as exc:
            _mark_submission_failed(locked_submission, str(exc))
            return locked_submission

        locked_submission.status = SabangnetOrderSubmission.Status.SENT
        locked_submission.sabangnet_order_no = response.sabangnet_order_no
        locked_submission.last_error_message = ""
        locked_submission.terminal_failure_at = None
        locked_submission.next_retry_at = None
        locked_submission.payload_summary = {
            **locked_submission.payload_summary,
            "response": response.raw_summary,
        }
        locked_submission.save(
            update_fields=[
                "status",
                "sabangnet_order_no",
                "last_error_message",
                "terminal_failure_at",
                "next_retry_at",
                "payload_summary",
                "updated_at",
            ]
        )
        order.sabangnet_status = "sent"
        order.save(update_fields=["sabangnet_status", "updated_at"])
        return locked_submission


def process_pending_order_submissions(client, limit=50):
    submissions = list(
        SabangnetOrderSubmission.objects.filter(
            status__in=[
                SabangnetOrderSubmission.Status.PENDING,
                SabangnetOrderSubmission.Status.RETRYING,
            ]
        )
        .select_related("order")
        .order_by("created_at")[:limit]
    )
    for submission in submissions:
        submit_order_submission(submission, client)
    return len(submissions)


def pending_order_submission_count():
    return SabangnetOrderSubmission.objects.filter(
        status__in=[
            SabangnetOrderSubmission.Status.PENDING,
            SabangnetOrderSubmission.Status.RETRYING,
        ]
    ).count()


def _mark_submission_failed(submission, message):
    submission.status = SabangnetOrderSubmission.Status.FAILED
    submission.last_error_message = message[:1000]
    submission.terminal_failure_at = timezone.now()
    submission.next_retry_at = None
    submission.save(
        update_fields=[
            "status",
            "last_error_message",
            "terminal_failure_at",
            "next_retry_at",
            "updated_at",
        ]
    )
    submission.order.sabangnet_status = "failed"
    submission.order.save(update_fields=["sabangnet_status", "updated_at"])


def _extract_sabangnet_order_no(data):
    for key in ["sabangnet_order_no", "sbOrderNo", "SB_ORD_NO", "orderNo"]:
        value = data.get(key)
        if value:
            return str(value)
    items = data.get("items")
    if isinstance(items, list) and items:
        first = items[0]
        if isinstance(first, dict):
            return _extract_sabangnet_order_no(first)
    return ""


def _safe_response_summary(data):
    if not isinstance(data, dict):
        return {"raw": str(data)[:500]}
    return {key: value for key, value in data.items() if key.lower() not in {"token", "access_token", "secret"}}
