import pytest

from catalog.models import Brand, Category, Product, ProductListing, ProductVariant
from commerce.models import Order, Payment, PaymentAttempt


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
def test_toss_confirm_marks_order_paid_and_queues_sabangnet_submission(api_client, order):
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
    assert PaymentAttempt.objects.get(order=order).status == PaymentAttempt.Status.CONFIRMED

    from integrations.models import SabangnetOrderSubmission

    submission = SabangnetOrderSubmission.objects.get(order=order)
    assert submission.status == SabangnetOrderSubmission.Status.PENDING
    assert submission.operation_idempotency_key == f"sabangnet-order:{order.order_number}"


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

    from integrations.models import SabangnetOrderSubmission

    assert SabangnetOrderSubmission.objects.filter(order=order).count() == 1


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
