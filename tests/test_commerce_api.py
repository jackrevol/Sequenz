import pytest

from accounts.models import WishlistItem
from catalog.models import Product, ProductListing, ProductVariant
from commerce.models import Cart, Order, PaymentAttempt


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
def test_cart_changes_option_and_merges_existing_item(api_client, listing_variant):
    second_variant = ProductVariant.objects.create(
        product=listing_variant.variant.product, variant_code="SEQ-P-2000-BLK-M",
        option_display_name="Black / M", stock_quantity=8, supply_status="SALE",
    )
    second_listing_variant = listing_variant.listing.variants.create(variant=second_variant, status="active")
    first = api_client.post(
        "/api/commerce/cart/items/", {"listing_variant_id":listing_variant.id, "quantity":1},
        format="json", HTTP_X_GUEST_KEY="option-cart",
    ).json()
    api_client.post(
        "/api/commerce/cart/items/", {"listing_variant_id":second_listing_variant.id, "quantity":2},
        format="json", HTTP_X_GUEST_KEY="option-cart",
    )

    changed = api_client.patch(
        f"/api/commerce/cart/items/{first['id']}/",
        {"listing_variant_id":second_listing_variant.id, "quantity":1},
        format="json", HTTP_X_GUEST_KEY="option-cart",
    )

    assert changed.status_code == 200
    assert changed.json()["listing_variant_id"] == second_listing_variant.id
    assert changed.json()["quantity"] == 3
    assert Cart.objects.get(status=Cart.Status.ACTIVE).items.count() == 1


@pytest.mark.django_db
def test_member_bulk_moves_selected_cart_items_to_wishlist(api_client, listing_variant, django_user_model):
    user = django_user_model.objects.create_user(username="bulk-cart", password="strong-pass-1234")
    api_client.force_login(user)
    item = api_client.post(
        "/api/commerce/cart/items/", {"listing_variant_id":listing_variant.id, "quantity":1}, format="json"
    ).json()

    moved = api_client.post(
        "/api/commerce/cart/items/bulk/",
        {"item_ids":[item["id"]], "action":"move_to_wishlist"}, format="json",
    )

    assert moved.status_code == 200
    assert moved.json()["processed_count"] == 1
    assert WishlistItem.objects.filter(user=user, listing=listing_variant.listing).exists()
    assert Cart.objects.get(user=user, status=Cart.Status.ACTIVE).items.count() == 0


@pytest.mark.django_db
def test_ordering_selected_items_preserves_remaining_cart(api_client, listing_variant):
    other_product = Product.objects.create(
        brand=listing_variant.listing.product.brand, category=listing_variant.listing.product.category,
        sabangnet_product_code="SB-OTHER", custom_product_code="OTHER", name="Other Product",
        consumer_price=30000, selling_price=30000, tax_code="TAXABLE", supply_status="IN_SUPPLY",
    )
    other_variant = ProductVariant.objects.create(
        product=other_product, variant_code="OTHER-ONE", option_display_name="One",
        stock_quantity=10, supply_status="SALE",
    )
    other_listing = ProductListing.objects.create(
        product=other_product, listing_code="OTHER-L", status="active", display_name="Other Product",
        slug="other-product", consumer_price_snapshot=30000, selling_price_snapshot=30000,
    )
    other_listing_variant = other_listing.variants.create(variant=other_variant, status="active")
    first = api_client.post(
        "/api/commerce/cart/items/", {"listing_variant_id":listing_variant.id, "quantity":1},
        format="json", HTTP_X_GUEST_KEY="selected-order",
    ).json()
    second = api_client.post(
        "/api/commerce/cart/items/", {"listing_variant_id":other_listing_variant.id, "quantity":1},
        format="json", HTTP_X_GUEST_KEY="selected-order",
    ).json()

    response = api_client.post(
        "/api/commerce/orders/",
        {
            "buyer_name":"Buyer", "buyer_phone":"01012345678", "recipient_name":"Receiver",
            "recipient_phone":"01012345678", "postal_code":"06000", "address1":"Seoul",
            "cart_item_ids":[first["id"]],
        },
        format="json", HTTP_X_GUEST_KEY="selected-order",
    )

    assert response.status_code == 201
    assert response.json()["items"][0]["product_name_snapshot"] == "Panel Rashguard"
    cart = Cart.objects.get(guest_key_hash__isnull=False, status=Cart.Status.ACTIVE)
    assert list(cart.items.values_list("id", flat=True)) == [second["id"]]


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

    lookup = api_client.post(
        "/api/commerce/orders/guest-lookup/",
        {"order_number": order.order_number, "buyer_name": "Hong Gildong", "buyer_phone": "010-1234-5678"},
        format="json",
    )
    assert lookup.status_code == 200
    assert lookup.json()["order_number"] == order.order_number

    wrong_phone = api_client.post(
        "/api/commerce/orders/guest-lookup/",
        {"order_number": order.order_number, "buyer_name": "Hong Gildong", "buyer_phone": "01000000000"},
        format="json",
    )
    assert wrong_phone.status_code == 404


@pytest.mark.django_db
def test_local_reservation_prevents_orders_exceeding_sabangnet_stock(api_client, listing_variant):
    payload = {
        "buyer_name": "Buyer", "buyer_phone": "01012345678",
        "recipient_name": "Receiver", "recipient_phone": "01012345678",
        "postal_code": "06000", "address1": "Seoul",
    }
    for guest_key in ("reserve-a", "reserve-b"):
        api_client.post(
            "/api/commerce/cart/items/",
            {"listing_variant_id": listing_variant.id, "quantity": 3},
            format="json", HTTP_X_GUEST_KEY=guest_key,
        )

    first = api_client.post(
        "/api/commerce/orders/", payload, format="json", HTTP_X_GUEST_KEY="reserve-a"
    )
    second = api_client.post(
        "/api/commerce/orders/", payload, format="json", HTTP_X_GUEST_KEY="reserve-b"
    )

    assert first.status_code == 201
    assert second.status_code == 409
    variant = listing_variant.variant
    variant.refresh_from_db()
    assert variant.stock_quantity == 5
    assert variant.reserved_quantity == 3
