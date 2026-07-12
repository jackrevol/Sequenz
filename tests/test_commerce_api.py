import pytest

from catalog.models import Brand, Category, Product, ProductListing, ProductVariant
from commerce.models import Cart, Order, PaymentAttempt


@pytest.fixture
def listing_variant(db):
    brand = Brand.objects.create(name="Sequenz", slug="sequenz", sort_order=1)
    category = Category.objects.create(name="Swimwear", slug="swimwear", level=1, sort_order=1)
    product = Product.objects.create(
        brand=brand,
        category=category,
        sabangnet_product_code="SB-P-2000",
        custom_product_code="SEQ-P-2000",
        name="Panel Rashguard",
        consumer_price=89000,
        selling_price=79000,
        tax_code="TAXABLE",
        supply_status="IN_SUPPLY",
    )
    variant = ProductVariant.objects.create(
        product=product,
        variant_code="SEQ-P-2000-WHT-L",
        barcode="880000000002",
        option_display_name="White / L",
        additional_amount=0,
        stock_quantity=5,
        safety_stock_quantity=1,
        supply_status="SALE",
    )
    listing = ProductListing.objects.create(
        product=product,
        listing_code="LIST-2000",
        sales_channel="main_mall",
        status="active",
        display_name="Panel Rashguard",
        slug="panel-rashguard",
        consumer_price_snapshot=89000,
        selling_price_snapshot=79000,
        price_source="sabangnet",
    )
    return listing.variants.create(
        variant=variant,
        status="active",
        additional_amount_snapshot=0,
        stock_display_policy="show",
        sort_order=1,
    )


@pytest.mark.django_db
def test_guest_cart_add_uses_listing_variant_and_price_snapshot(api_client, listing_variant):
    response = api_client.post(
        "/api/commerce/cart/items/",
        {"listing_variant_id": listing_variant.id, "quantity": 2},
        format="json",
        HTTP_X_GUEST_KEY="guest-1",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["quantity"] == 2
    assert body["unit_price_snapshot"] == listing_variant.listing.selling_price_snapshot
    assert Cart.objects.get(guest_key_hash__isnull=False).items.count() == 1


@pytest.mark.django_db
def test_guest_cart_can_update_delete_and_returns_summary(api_client, listing_variant):
    created = api_client.post(
        "/api/commerce/cart/items/",
        {"listing_variant_id": listing_variant.id, "quantity": 1},
        format="json",
        HTTP_X_GUEST_KEY="guest-cart-edit",
    ).json()

    updated = api_client.patch(
        f"/api/commerce/cart/items/{created['id']}/",
        {"quantity": 3},
        format="json",
        HTTP_X_GUEST_KEY="guest-cart-edit",
    )
    cart = api_client.get("/api/commerce/cart/items/", HTTP_X_GUEST_KEY="guest-cart-edit")

    assert updated.status_code == 200
    assert cart.json()["summary"]["item_count"] == 3
    assert cart.json()["summary"]["payment_amount"] == 237000

    deleted = api_client.delete(
        f"/api/commerce/cart/items/{created['id']}/",
        HTTP_X_GUEST_KEY="guest-cart-edit",
    )
    assert deleted.status_code == 204


@pytest.mark.django_db
def test_order_rejects_stale_cart_price(api_client, listing_variant):
    api_client.post(
        "/api/commerce/cart/items/",
        {"listing_variant_id": listing_variant.id, "quantity": 1},
        format="json", HTTP_X_GUEST_KEY="stale-price",
    )
    listing_variant.listing.selling_price_snapshot += 1000
    listing_variant.listing.save(update_fields=["selling_price_snapshot"])
    response = api_client.post(
        "/api/commerce/orders/",
        {"buyer_name":"Buyer", "buyer_phone":"01000000000", "recipient_name":"Receiver", "recipient_phone":"01000000000", "postal_code":"06000", "address1":"Seoul"},
        format="json", HTTP_X_GUEST_KEY="stale-price",
    )
    assert response.status_code == 409
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_order_creation_snapshots_listing_and_creates_payment_attempt(api_client, listing_variant):
    api_client.post(
        "/api/commerce/cart/items/",
        {"listing_variant_id": listing_variant.id, "quantity": 1},
        format="json",
        HTTP_X_GUEST_KEY="guest-order",
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
        HTTP_X_GUEST_KEY="guest-order",
    )

    assert response.status_code == 201
    order = Order.objects.get(order_number=response.json()["order_number"])
    assert order.items.count() == 1
    assert order.items.first().listing_code_snapshot == listing_variant.listing.listing_code
    assert order.payment_amount == listing_variant.listing.selling_price_snapshot
    assert PaymentAttempt.objects.filter(order=order, expected_amount=order.payment_amount).exists()

    detail = api_client.get(
        f"/api/commerce/orders/{order.order_number}/",
        HTTP_X_GUEST_KEY="guest-order",
    )
    assert detail.status_code == 200
    assert detail.json()["items"][0]["product_name_snapshot"] == "Panel Rashguard"

    hidden = api_client.get(
        f"/api/commerce/orders/{order.order_number}/",
        HTTP_X_GUEST_KEY="another-guest",
    )
    assert hidden.status_code == 404
