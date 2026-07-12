import json
from dataclasses import dataclass
from datetime import date
from urllib import error, request

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from commerce.models import Order, OrderStatusHistory


class SabangnetStatusError(Exception):
    pass


@dataclass(frozen=True)
class StatusSyncResult:
    matched: int = 0
    updated: int = 0
    unknown_statuses: int = 0


class SabangnetOrderStatusClient:
    def __init__(self, base_url=None, bearer_token=None, service_account_id=None, timeout=15):
        self.base_url = base_url or settings.SABANGNET_API_BASE_URL
        self.bearer_token = bearer_token or settings.SABANGNET_BEARER_TOKEN
        self.service_account_id = service_account_id or settings.SABANGNET_SVC_ACCOUNT_ID
        self.timeout = timeout

    def fetch_orders(self, start_date, end_date, page=1, per_page=100):
        if not self.base_url or not self.bearer_token or not self.service_account_id:
            raise SabangnetStatusError("사방넷 주문조회 API 환경변수가 설정되지 않았습니다.")
        payload = {
            "startDate": _compact_date(start_date),
            "endDate": _compact_date(end_date),
            "dateSearchCondition": 3,
            "page": page,
            "perPage": per_page,
            "updateOrderStsYn": "N",
            "responseItems": ["SB_ORD_NO", "SHOP_ORD_NO", "ORDER_STATUS"],
        }
        http_request = request.Request(
            f"{self.base_url.rstrip('/')}/v3/sb/order",
            data=json.dumps(payload).encode(),
            method="GET",
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "X-Svc-Acnt-Id": self.service_account_id,
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode())
        except error.HTTPError as exc:
            raise SabangnetStatusError(f"사방넷 주문조회가 HTTP {exc.code}로 실패했습니다.") from exc
        except (error.URLError, TimeoutError, ValueError) as exc:
            raise SabangnetStatusError("사방넷 주문조회 응답을 처리하지 못했습니다.") from exc
        return _extract_order_rows(body)


def configured_status_map():
    raw = settings.SABANGNET_ORDER_STATUS_MAP
    if isinstance(raw, dict):
        mapping = raw
    else:
        try:
            mapping = json.loads(raw or "{}")
        except (TypeError, ValueError) as exc:
            raise SabangnetStatusError("SABANGNET_ORDER_STATUS_MAP은 JSON 객체여야 합니다.") from exc
    allowed = set(Order.FulfillmentStatus.values)
    invalid = {key: value for key, value in mapping.items() if value not in allowed}
    if invalid:
        raise SabangnetStatusError(f"지원하지 않는 내부 배송상태 매핑입니다: {invalid}")
    return {str(key): value for key, value in mapping.items()}


def sync_order_status_rows(rows, status_map=None):
    status_map = status_map if status_map is not None else configured_status_map()
    matched = updated = unknown = 0
    for row in rows:
        shop_order_no = str(row.get("SHOP_ORD_NO") or row.get("shopOrderNo") or "").strip()
        raw_status = str(row.get("ORDER_STATUS") or row.get("orderStatus") or "").strip()
        sabangnet_order_no = str(row.get("SB_ORD_NO") or row.get("sbOrderNo") or "").strip()
        if not shop_order_no or not raw_status:
            continue
        try:
            order = Order.objects.get(order_number=shop_order_no)
        except Order.DoesNotExist:
            continue
        matched += 1
        mapped = status_map.get(raw_status)
        if mapped is None:
            unknown += 1
        if _update_order_status(order.pk, raw_status, sabangnet_order_no, mapped):
            updated += 1
    return StatusSyncResult(matched=matched, updated=updated, unknown_statuses=unknown)


@transaction.atomic
def _update_order_status(order_id, raw_status, sabangnet_order_no, mapped_status):
    order = Order.objects.select_for_update().get(pk=order_id)
    previous = order.fulfillment_status
    changed = order.sabangnet_order_status != raw_status or order.sabangnet_order_no != sabangnet_order_no
    order.sabangnet_order_status = raw_status
    order.sabangnet_order_no = sabangnet_order_no or order.sabangnet_order_no
    order.sabangnet_status_synced_at = timezone.now()
    update_fields = ["sabangnet_order_status", "sabangnet_order_no", "sabangnet_status_synced_at", "updated_at"]
    if mapped_status and mapped_status != previous:
        order.fulfillment_status = mapped_status
        update_fields.append("fulfillment_status")
        OrderStatusHistory.objects.create(
            order=order,
            source=OrderStatusHistory.Source.SABANGNET,
            previous_status=previous,
            new_status=mapped_status,
            raw_external_status=raw_status,
        )
        changed = True
    order.save(update_fields=update_fields)
    return changed


def _extract_order_rows(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("items", "results", "data", "orderList", "orders"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_order_rows(value)
            if nested:
                return nested
    return []


def _compact_date(value):
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    return str(value).replace("-", "")
