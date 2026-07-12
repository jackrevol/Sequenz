import pytest

from catalog.models import Brand, Category, Product, ProductListing, ProductVariant
from commerce.models import Order, OrderCancellation, Payment, PaymentAttempt


@pytest.fixture(autouse=True)
def fake_toss_confirm(monkeypatch):
    monkeypatch.setattr(
        "commerce.views.confirm_toss_payment",
        lambda payment_key, order_id, amount: {
            "paymentKey": payment_key,
            "orderId": order_id,
            "status": "DONE",
            "method": "카드",
            "totalAmount": amount,
            "balanceAmount": amount,
        },
    )


@pytest.fixture
def listing_variant(db):
    brand = Brand.objects.create(name="Sequenz", slug="sequenz-payment", sort_order=1)
    category = Category.objects.create(name="Swimwear", slug="swimwear-payment", level=1, sort_order=1)
    product = Product.objects.create(
        brand=brand,
        category=category,
        sabangnet_product_code="SB-PAY-1000",
        custom_product_code="SEQ-PAY-1000",
        name="Payment Rashguard",
        consumer_price=99000,
        selling_price=88000,
        tax_code="TAXABLE",
        supply_status="IN_SUPPLY",
    )
    variant = ProductVariant.objects.create(
        product=product,
        variant_code="SEQ-PAY-1000-BLK-M",
        barcode="880000001000",
        option_display_name="Black / M",
        additional_amount=0,
        stock_quantity=4,
        safety_stock_quantity=1,
        supply_status="SALE",
    )
    listing = ProductListing.objects.create(
        product=product,
        listing_code="LIST-PAY-1000",
        sales_channel="main_mall",
        status="active",
        display_name="Payment Rashguard",
        slug="payment-rashguard",
        consumer_price_snapshot=99000,
        selling_price_snapshot=88000,
        price_source="sabangnet",
    )
    return listing.variants.create(
        variant=variant,
        status="active",
        additional_amount_snapshot=0,
        stock_display_policy="show",
        sort_order=1,
    )


@pytest.fixture
def order(api_client, listing_variant):
    api_client.credentials(HTTP_X_GUEST_KEY="payment-guest")
    api_client.post(
        "/api/commerce/cart/items/",
        {"listing_variant_id": listing_variant.id, "quantity": 1},
        format="json",
        HTTP_X_GUEST_KEY="payment-guest",
    )
    response = api_client.post(
        "/api/commerce/orders/",
        {
            "buyer_name": "Hong Gildong",
            "buyer_phone": "01012345678",
            "buyer_email": "buyer@example.com",
            "recipient_name": "Hong Gildong",
            "recipient_phone": "01012345678",
            "postal_code": "06000",
            "address1": "Seoul",
            "address2": "Gangnam",
            "delivery_memo": "door",
        },
        format="json",
        HTTP_X_GUEST_KEY="payment-guest",
    )
    return Order.objects.get(order_number=response.json()["order_number"])


@pytest.mark.django_db
def test_toss_confirm_marks_order_paid_and_queues_sabangnet_export(api_client, order):
    response = api_client.post(
        "/api/commerce/payments/toss/confirm/",
        {
            "order_number": order.order_number,
            "payment_key": "pay_test_1000",
            "amount": order.payment_amount,
            "method": "카드",
        },
        format="json",
    )

    assert response.status_code == 201
    order.refresh_from_db()
    assert order.status == Order.Status.PAID
    assert Payment.objects.filter(order=order, payment_key="pay_test_1000", status="DONE").exists()
    assert order.paid_at is not None
    assert PaymentAttempt.objects.get(order=order).status == PaymentAttempt.Status.CONFIRMED

    from integrations.models import SabangnetOrderExport

    export = SabangnetOrderExport.objects.get(order=order)
    assert export.status == SabangnetOrderExport.Status.PENDING


@pytest.mark.django_db
def test_toss_confirm_is_idempotent_for_same_payment_key(api_client, order):
    payload = {
        "order_number": order.order_number,
        "payment_key": "pay_test_repeat",
        "amount": order.payment_amount,
        "method": "카드",
    }
    first = api_client.post("/api/commerce/payments/toss/confirm/", payload, format="json")
    second = api_client.post("/api/commerce/payments/toss/confirm/", payload, format="json")

    assert first.status_code == 201
    assert second.status_code == 200
    assert Payment.objects.filter(order=order, payment_key="pay_test_repeat").count() == 1

    from integrations.models import SabangnetOrderExport

    assert SabangnetOrderExport.objects.filter(order=order).count() == 1


@pytest.mark.django_db
def test_toss_confirm_rejects_amount_mismatch(api_client, order):
    response = api_client.post(
        "/api/commerce/payments/toss/confirm/",
        {
            "order_number": order.order_number,
            "payment_key": "pay_test_wrong_amount",
            "amount": order.payment_amount + 1,
            "method": "카드",
        },
        format="json",
    )

    assert response.status_code == 400
    order.refresh_from_db()
    assert order.status == Order.Status.PAYMENT_PENDING
    assert Payment.objects.filter(order=order).count() == 0


@pytest.mark.django_db
def test_toss_confirm_rejects_mismatched_provider_response(api_client, order, monkeypatch):
    monkeypatch.setattr(
        "commerce.views.confirm_toss_payment",
        lambda *args: {"paymentKey": "different", "orderId": order.order_number, "status": "DONE", "totalAmount": order.payment_amount},
    )
    response = api_client.post(
        "/api/commerce/payments/toss/confirm/",
        {"order_number": order.order_number, "payment_key": "pay_expected", "amount": order.payment_amount},
        format="json",
    )
    assert response.status_code == 502
    order.refresh_from_db()
    assert order.status == Order.Status.PAYMENT_PENDING
    assert Payment.objects.filter(order=order).count() == 0


@pytest.mark.django_db
def test_toss_prepare_uses_server_order_amount_and_hides_secret(api_client, order, settings):
    settings.TOSS_CLIENT_KEY = "test_ck_example"
    response = api_client.get(
        f"/api/commerce/payments/toss/prepare/{order.order_number}/",
        HTTP_X_GUEST_KEY="payment-guest",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["client_key"] == "test_ck_example"
    assert body["customer_key"] == "ANONYMOUS"
    assert body["amount"] == order.payment_amount
    assert "secret_key" not in body


@pytest.mark.django_db
def test_paid_order_can_be_fully_cancelled_once(api_client, order, monkeypatch):
    confirmed = api_client.post(
        "/api/commerce/payments/toss/confirm/",
        {"order_number": order.order_number, "payment_key": "pay_cancel", "amount": order.payment_amount},
        format="json",
    )
    assert confirmed.status_code == 201
    calls = []

    def fake_cancel(payment_key, reason, idempotency_key):
        calls.append((payment_key, reason, idempotency_key))
        return {
            "status": "CANCELED", "balanceAmount": 0,
            "cancels": [{"transactionKey": "cancel_tx_1", "cancelAmount": order.payment_amount}],
        }

    monkeypatch.setattr("commerce.views.cancel_toss_payment", fake_cancel)
    first = api_client.post(
        f"/api/commerce/orders/{order.order_number}/cancel/",
        {"reason": "고객 요청"},
        format="json",
        HTTP_X_GUEST_KEY="payment-guest",
    )
    second = api_client.post(
        f"/api/commerce/orders/{order.order_number}/cancel/",
        {"reason": "중복 요청"},
        format="json",
        HTTP_X_GUEST_KEY="payment-guest",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(calls) == 1
    order.refresh_from_db()
    assert order.status == Order.Status.CANCELLED
    assert order.fulfillment_status == Order.FulfillmentStatus.CANCELLED
    assert OrderCancellation.objects.get(order=order).transaction_key == "cancel_tx_1"
    assert Payment.objects.get(order=order).status == "CANCELED"


@pytest.mark.django_db
def test_shipped_order_cannot_be_immediately_cancelled(api_client, order):
    api_client.post(
        "/api/commerce/payments/toss/confirm/",
        {"order_number": order.order_number, "payment_key": "pay_shipped", "amount": order.payment_amount},
        format="json",
    )
    order.fulfillment_status = Order.FulfillmentStatus.SHIPPED
    order.save(update_fields=["fulfillment_status"])
    response = api_client.post(
        f"/api/commerce/orders/{order.order_number}/cancel/",
        {"reason": "배송 후 요청"},
        format="json",
        HTTP_X_GUEST_KEY="payment-guest",
    )
    assert response.status_code == 409
