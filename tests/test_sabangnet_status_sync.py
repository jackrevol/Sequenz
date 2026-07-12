import pytest

from commerce.models import Order, OrderStatusHistory
from integrations.sabangnet_status import SabangnetStatusError, configured_status_map, sync_order_status_rows


@pytest.fixture
def paid_order(db):
    return Order.objects.create(
        order_number="SEQ-STATUS-1", status=Order.Status.PAID,
        buyer_name="Buyer", buyer_phone="01000000000", recipient_name="Receiver",
        recipient_phone="01000000000", postal_code="06000", address1="Seoul",
        payment_amount=10000,
    )


@pytest.mark.django_db
def test_sync_preserves_raw_status_and_maps_approved_delivery_status(paid_order):
    result = sync_order_status_rows(
        [{"SHOP_ORD_NO": paid_order.order_number, "SB_ORD_NO": "SB-100", "ORDER_STATUS": "DELIVERY_DONE"}],
        status_map={"DELIVERY_DONE": Order.FulfillmentStatus.DELIVERED},
    )

    paid_order.refresh_from_db()
    assert result.matched == 1
    assert result.updated == 1
    assert result.unknown_statuses == 0
    assert paid_order.sabangnet_order_no == "SB-100"
    assert paid_order.sabangnet_order_status == "DELIVERY_DONE"
    assert paid_order.fulfillment_status == Order.FulfillmentStatus.DELIVERED
    history = OrderStatusHistory.objects.get(order=paid_order)
    assert history.previous_status == Order.FulfillmentStatus.PENDING
    assert history.new_status == Order.FulfillmentStatus.DELIVERED


@pytest.mark.django_db
def test_unknown_sabangnet_status_is_stored_without_guessing_mapping(paid_order):
    result = sync_order_status_rows(
        [{"SHOP_ORD_NO": paid_order.order_number, "ORDER_STATUS": "UNCONFIRMED_999"}],
        status_map={},
    )
    paid_order.refresh_from_db()
    assert result.unknown_statuses == 1
    assert paid_order.sabangnet_order_status == "UNCONFIRMED_999"
    assert paid_order.fulfillment_status == Order.FulfillmentStatus.PENDING
    assert OrderStatusHistory.objects.count() == 0


def test_status_map_rejects_invalid_internal_status(settings):
    settings.SABANGNET_ORDER_STATUS_MAP = '{"001":"made_up"}'
    with pytest.raises(SabangnetStatusError):
        configured_status_map()
