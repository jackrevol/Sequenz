from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from commerce.models import Order, OrderClaim, Payment


def _create_paid_order(api_client, user, listing_variant, quantity=2):
    api_client.force_authenticate(user)
    api_client.post(
        "/api/commerce/cart/items/",
        {"listing_variant_id": listing_variant.id, "quantity": quantity},
        format="json",
    )
    response = api_client.post(
        "/api/commerce/orders/",
        {
            "buyer_name": "Member", "buyer_phone": "01012345678",
            "recipient_name": "Member", "recipient_phone": "01012345678",
            "postal_code": "06000", "address1": "Seoul",
        },
        format="json",
    )
    order = Order.objects.get(order_number=response.json()["order_number"])
    order.status = Order.Status.PAID
    order.save(update_fields=["status"])
    payment = Payment.objects.create(
        order=order, payment_key=f"payment-{order.id}", toss_order_id=order.order_number,
        status="DONE", total_amount=order.payment_amount, balance_amount=order.payment_amount,
    )
    return order, payment


@pytest.mark.django_db
def test_partial_cancel_refunds_selected_quantity(api_client, listing_variant):
    user = get_user_model().objects.create_user("claim-member", password="password")
    order, payment = _create_paid_order(api_client, user, listing_variant)
    item = order.items.get()
    toss_response = {
        "status": "PARTIAL_CANCELED",
        "balanceAmount": 79000,
        "cancels": [{"transactionKey": "partial-tx"}],
    }

    with patch("commerce.views.cancel_toss_payment", return_value=toss_response) as cancel:
        response = api_client.post(
            f"/api/commerce/orders/{order.order_number}/claims/",
            {
                "claim_type": "partial_cancel", "reason": "옵션 변경",
                "items": [{"order_item_id": item.id, "quantity": 1}],
            },
            format="json",
        )

    assert response.status_code == 201
    assert response.json()["status"] == OrderClaim.Status.COMPLETED
    assert response.json()["refund_amount"] == 79000
    cancel.assert_called_once_with(payment.payment_key, "옵션 변경", cancel.call_args.args[2], cancel_amount=79000)
    item.refresh_from_db()
    payment.refresh_from_db()
    assert item.cancelled_quantity == 1
    assert payment.balance_amount == 79000


@pytest.mark.django_db
def test_return_request_is_recorded_without_payment_cancel(api_client, listing_variant):
    user = get_user_model().objects.create_user("return-member", password="password")
    order, _ = _create_paid_order(api_client, user, listing_variant, quantity=1)
    order.fulfillment_status = Order.FulfillmentStatus.DELIVERED
    order.save(update_fields=["fulfillment_status"])
    item = order.items.get()

    response = api_client.post(
        f"/api/commerce/orders/{order.order_number}/claims/",
        {
            "claim_type": "return", "reason": "사이즈 불일치", "detail": "미착용 상품",
            "items": [{"order_item_id": item.id, "quantity": 1}],
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["status"] == OrderClaim.Status.REQUESTED
    listed = api_client.get(f"/api/commerce/orders/{order.order_number}/claims/")
    assert listed.status_code == 200
    assert listed.json()["results"][0]["claim_type"] == "return"
