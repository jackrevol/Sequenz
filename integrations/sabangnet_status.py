import json
from dataclasses import dataclass
from datetime import date

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from commerce.models import Order, OrderStatusHistory, Shipment
from integrations.sabangnet_client import SabangnetApiClient, SabangnetApiError, extract_data_list


class SabangnetStatusError(Exception):
    pass


@dataclass(frozen=True)
class StatusSyncResult:
    matched: int = 0
    updated: int = 0
    unknown_statuses: int = 0


class SabangnetOrderStatusClient:
    def __init__(self, base_url=None, bearer_token=None, service_account_id=None, timeout=None, api_client=None):
        self.api_client = api_client or SabangnetApiClient(
            base_url=base_url,
            bearer_token=bearer_token,
            service_account_id=service_account_id,
            timeout=timeout,
        )

    def fetch_orders(self, start_date, end_date, page=1, per_page=100):
        response_items = ["SB_ORD_NO", "SHOP_ORD_NO", "ORDER_STATUS"]
        response_items.extend(_configured_shipment_response_items())
        payload = {
            "startDate": _compact_date(start_date),
            "endDate": _compact_date(end_date),
            "dateSearchCondition": 3,
            "page": page,
            "perPage": per_page,
            "updateOrderStsYn": "N",
            "responseItems": list(dict.fromkeys(response_items)),
        }
        try:
            body = self.api_client.request_json("GET", "/order", json_body=payload)
        except SabangnetApiError as exc:
            raise SabangnetStatusError(str(exc)) from exc
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
        status_changed = _update_order_status(order.pk, raw_status, sabangnet_order_no, mapped)
        shipment_changed = _sync_shipment(order.pk, row, sabangnet_order_no, mapped or raw_status)
        if status_changed or shipment_changed:
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
    if mapped_status == Order.FulfillmentStatus.DELIVERED and previous != Order.FulfillmentStatus.DELIVERED:
        from benefits.services import complete_delivered_order_benefits

        complete_delivered_order_benefits(order)
    elif mapped_status == Order.FulfillmentStatus.RETURNED and previous != Order.FulfillmentStatus.RETURNED:
        from benefits.services import reverse_delivered_order_benefits

        reverse_delivered_order_benefits(order)
    return changed


@transaction.atomic
def _sync_shipment(order_id, row, sabangnet_order_no, shipment_status):
    tracking_number = _first_text(
        row, "WAYBILL_NO", "WAY_BILL_NO", "INVOICE_NO", "TRACKING_NO", "SHIPPING_CODE",
        "wayBillNo", "invoiceNo", "trackingNumber", "shippingCode",
    )
    if not tracking_number:
        return False
    carrier_code = _first_text(
        row, "DELIVERY_COMPANY_CODE", "DELIVERY_AGENCY_ID", "CARRIER_CODE",
        "LOGISTICS_CD", "LOGISTICS_ID",
        "deliveryCompanyCode", "deliveryAgencyId", "carrierCode", "logisticsCode", "logisticsId",
    )
    carrier_name = _first_text(
        row, "DELIVERY_COMPANY_NAME", "DELIVERY_AGENCY_NAME", "CARRIER_NAME",
        "LOGISTICS_NM",
        "deliveryCompanyName", "deliveryAgencyName", "carrierName", "logisticsName",
    )
    existing = Shipment.objects.filter(
        order_id=order_id, carrier_code=carrier_code, tracking_number=tracking_number
    ).first()
    now = timezone.now()
    defaults = {
        "sabangnet_order_no": sabangnet_order_no,
        "carrier_name": carrier_name,
        "status": shipment_status,
        "raw_summary": {
            "tracking_number": tracking_number,
            "carrier_code": carrier_code,
            "carrier_name": carrier_name,
            "external_status": _first_text(row, "ORDER_STATUS", "orderStatus"),
        },
    }
    if shipment_status in {
        Order.FulfillmentStatus.SHIPPED,
        Order.FulfillmentStatus.IN_TRANSIT,
        Order.FulfillmentStatus.DELIVERED,
    }:
        defaults["shipped_at"] = existing.shipped_at if existing and existing.shipped_at else now
    if shipment_status == Order.FulfillmentStatus.DELIVERED:
        defaults["delivered_at"] = existing.delivered_at if existing and existing.delivered_at else now
    changed = existing is None or any(getattr(existing, key) != value for key, value in defaults.items())
    Shipment.objects.update_or_create(
        order_id=order_id,
        carrier_code=carrier_code,
        tracking_number=tracking_number,
        defaults=defaults,
    )
    return changed


def _extract_order_rows(payload):
    rows = extract_data_list(payload)
    if rows:
        return rows
    if isinstance(payload, dict):
        for key in ("response", "orderList"):
            nested = _extract_order_rows(payload.get(key))
            if nested:
                return nested
    return payload if isinstance(payload, list) else []


def _compact_date(value):
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    return str(value).replace("-", "")


def _configured_shipment_response_items():
    raw = settings.SABANGNET_ORDER_SHIPMENT_RESPONSE_ITEMS
    if isinstance(raw, list):
        items = raw
    else:
        try:
            items = json.loads(raw or "[]")
        except (TypeError, ValueError) as exc:
            raise SabangnetStatusError("SABANGNET_ORDER_SHIPMENT_RESPONSE_ITEMS는 JSON 배열이어야 합니다.") from exc
    if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
        raise SabangnetStatusError("SABANGNET_ORDER_SHIPMENT_RESPONSE_ITEMS는 문자열 JSON 배열이어야 합니다.")
    return items


def _first_text(row, *keys):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""
