from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from benefits.models import Coupon, MemberBenefitAccount, MemberCoupon, MemberTier, PointLedger, ShippingPolicy
from benefits.services import complete_delivered_order_benefits, restore_order_benefits, reverse_delivered_order_benefits
from commerce.models import Order


def _order_payload(**overrides):
    payload = {
        "buyer_name": "Member",
        "buyer_phone": "01012345678",
        "buyer_email": "member@example.com",
        "recipient_name": "Member",
        "recipient_phone": "01012345678",
        "postal_code": "06000",
        "address1": "Seoul",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_cart_summary_uses_default_shipping_policy(api_client, listing_variant):
    ShippingPolicy.objects.create(
        name="기본 배송", base_fee=3000, free_shipping_threshold=100000, is_default=True
    )

    api_client.post(
        "/api/commerce/cart/items/",
        {"listing_variant_id": listing_variant.id, "quantity": 1},
        format="json",
        HTTP_X_GUEST_KEY="shipping-policy",
    )
    summary = api_client.get(
        "/api/commerce/cart/items/", HTTP_X_GUEST_KEY="shipping-policy"
    ).json()["summary"]

    assert summary == {
        "item_count": 1,
        "items_subtotal": 79000,
        "shipping_fee": 3000,
        "payment_amount": 82000,
    }


@pytest.mark.django_db
def test_member_order_applies_coupon_and_points_and_restores_them(api_client, listing_variant):
    user = get_user_model().objects.create_user("member", password="password")
    account = MemberBenefitAccount.objects.create(user=user, point_balance=5000)
    coupon = Coupon.objects.create(
        name="첫 구매 10%", code="WELCOME10", discount_type=Coupon.DiscountType.PERCENT,
        discount_value=10, maximum_discount_amount=10000,
    )
    issued = MemberCoupon.objects.create(user=user, coupon=coupon)
    ShippingPolicy.objects.create(
        name="기본 배송", base_fee=3000, free_shipping_threshold=100000, is_default=True
    )
    api_client.force_authenticate(user)
    api_client.post(
        "/api/commerce/cart/items/",
        {"listing_variant_id": listing_variant.id, "quantity": 1},
        format="json",
    )

    quote = api_client.post(
        "/api/commerce/cart/benefit-quote/",
        {"coupon_code": "WELCOME10", "point_to_use": 2000},
        format="json",
    )
    assert quote.status_code == 200
    assert quote.json()["payment_amount"] == 72100

    response = api_client.post(
        "/api/commerce/orders/",
        _order_payload(coupon_code="WELCOME10", point_to_use=2000),
        format="json",
    )

    assert response.status_code == 201
    order = Order.objects.get(order_number=response.json()["order_number"])
    assert (order.shipping_fee, order.coupon_discount_amount, order.point_used_amount, order.payment_amount) == (
        3000, 7900, 2000, 72100,
    )
    issued.refresh_from_db()
    account.refresh_from_db()
    assert issued.status == MemberCoupon.Status.USED
    assert account.point_balance == 3000
    assert PointLedger.objects.get(order=order, reason=PointLedger.Reason.ORDER_USE).amount == -2000

    restore_order_benefits(order)
    restore_order_benefits(order)
    issued.refresh_from_db()
    account.refresh_from_db()
    assert issued.status == MemberCoupon.Status.AVAILABLE
    assert account.point_balance == 5000
    assert PointLedger.objects.filter(order=order, reason=PointLedger.Reason.CANCEL_RESTORE).count() == 1


@pytest.mark.django_db
def test_delivered_order_earns_points_and_updates_tier_once():
    user = get_user_model().objects.create_user("delivered", password="password")
    tier = MemberTier.objects.create(
        name="Silver", code="silver", minimum_purchase_amount=50000,
        minimum_order_count=1, point_earn_rate=Decimal("2.50"),
    )
    order = Order.objects.create(
        order_number=Order.new_order_number(), user=user, buyer_name="Buyer", buyer_phone="010",
        recipient_name="Receiver", recipient_phone="010", postal_code="06000", address1="Seoul",
        items_subtotal=80000, payment_amount=80000,
    )

    complete_delivered_order_benefits(order)
    complete_delivered_order_benefits(order)

    account = MemberBenefitAccount.objects.get(user=user)
    assert account.tier == tier
    assert account.lifetime_purchase_amount == 80000
    assert account.completed_order_count == 1
    assert account.point_balance == 2000
    assert PointLedger.objects.filter(order=order, reason=PointLedger.Reason.ORDER_EARN).count() == 1

    reverse_delivered_order_benefits(order)
    reverse_delivered_order_benefits(order)
    account.refresh_from_db()
    assert account.lifetime_purchase_amount == 0
    assert account.completed_order_count == 0
    assert account.point_balance == 0
    assert account.tier is None
    assert PointLedger.objects.filter(order=order, reason=PointLedger.Reason.ORDER_EARN_REVERSAL).count() == 1
