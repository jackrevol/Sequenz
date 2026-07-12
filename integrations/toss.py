import base64
import json
from urllib import error, request

from django.conf import settings


class TossPaymentError(Exception):
    def __init__(self, message, code="TOSS_CONFIRM_FAILED"):
        super().__init__(message)
        self.code = code


def confirm_toss_payment(payment_key, order_id, amount):
    secret_key = settings.TOSS_SECRET_KEY
    if not secret_key:
        raise TossPaymentError("토스페이먼츠 시크릿 키가 설정되지 않았습니다.", "TOSS_NOT_CONFIGURED")
    credentials = base64.b64encode(f"{secret_key}:".encode()).decode()
    body = json.dumps({"paymentKey": payment_key, "orderId": order_id, "amount": amount}).encode()
    http_request = request.Request(
        settings.TOSS_CONFIRM_URL,
        data=body,
        method="POST",
        headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/json"},
    )
    try:
        with request.urlopen(http_request, timeout=10) as response:
            return json.loads(response.read().decode())
    except error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode())
        except (ValueError, UnicodeDecodeError):
            payload = {}
        raise TossPaymentError(payload.get("message", "결제 승인에 실패했습니다."), payload.get("code", "TOSS_CONFIRM_FAILED")) from exc
    except (error.URLError, TimeoutError, ValueError) as exc:
        raise TossPaymentError("결제 승인 서버에 연결하지 못했습니다.", "TOSS_NETWORK_ERROR") from exc


def cancel_toss_payment(payment_key, reason, idempotency_key, cancel_amount=None):
    secret_key = settings.TOSS_SECRET_KEY
    if not secret_key:
        raise TossPaymentError("토스페이먼츠 시크릿 키가 설정되지 않았습니다.", "TOSS_NOT_CONFIGURED")
    credentials = base64.b64encode(f"{secret_key}:".encode()).decode()
    payload = {"cancelReason": reason}
    if cancel_amount is not None:
        payload["cancelAmount"] = cancel_amount
    body = json.dumps(payload).encode()
    url = f"https://api.tosspayments.com/v1/payments/{payment_key}/cancel"
    http_request = request.Request(
        url, data=body, method="POST",
        headers={
            "Authorization": f"Basic {credentials}", "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        },
    )
    try:
        with request.urlopen(http_request, timeout=10) as response:
            return json.loads(response.read().decode())
    except error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode())
        except (ValueError, UnicodeDecodeError):
            payload = {}
        raise TossPaymentError(payload.get("message", "결제 취소에 실패했습니다."), payload.get("code", "TOSS_CANCEL_FAILED")) from exc
    except (error.URLError, TimeoutError, ValueError) as exc:
        raise TossPaymentError("결제 취소 서버에 연결하지 못했습니다.", "TOSS_NETWORK_ERROR") from exc


def fetch_toss_payment(payment_key):
    secret_key = settings.TOSS_SECRET_KEY
    if not secret_key:
        raise TossPaymentError("토스페이먼츠 시크릿 키가 설정되지 않았습니다.", "TOSS_NOT_CONFIGURED")
    credentials = base64.b64encode(f"{secret_key}:".encode()).decode()
    http_request = request.Request(
        f"https://api.tosspayments.com/v1/payments/{payment_key}",
        headers={"Authorization": f"Basic {credentials}"},
    )
    try:
        with request.urlopen(http_request, timeout=10) as response:
            return json.loads(response.read().decode())
    except error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode())
        except (ValueError, UnicodeDecodeError):
            payload = {}
        raise TossPaymentError(payload.get("message", "결제 조회에 실패했습니다."), payload.get("code", "TOSS_LOOKUP_FAILED")) from exc
    except (error.URLError, TimeoutError, ValueError) as exc:
        raise TossPaymentError("결제 조회 서버에 연결하지 못했습니다.", "TOSS_NETWORK_ERROR") from exc
