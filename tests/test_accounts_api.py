import pytest

from accounts.models import MemberProfile, SocialConnection
from catalog.models import Brand, Category, Product, ProductListing, ProductVariant
from commerce.models import Cart
from commerce.models import Order


REGISTRATION = {
    "username": "sequenz_member",
    "email": "member@example.com",
    "password": "strong-pass-1234",
    "name": "Sequenz Member",
    "phone": "01011112222",
    "terms_agreed": True,
    "marketing_agreed": False,
}


@pytest.mark.django_db
def test_member_registers_before_social_connection(api_client):
    response = api_client.post("/api/accounts/register/", REGISTRATION, format="json")

    assert response.status_code == 201
    assert response.json()["username"] == "sequenz_member"
    assert response.json()["social_connections"] == {"kakao": False, "naver": False}
    assert MemberProfile.objects.get(user__username="sequenz_member").phone == "01011112222"

    me = api_client.get("/api/accounts/me/")
    assert me.status_code == 200

    social = api_client.post("/api/accounts/social/kakao/connect/", {}, format="json")
    assert social.status_code == 501
    assert SocialConnection.objects.count() == 0


@pytest.mark.django_db
def test_social_connection_requires_existing_login(api_client):
    response = api_client.post("/api/accounts/social/naver/connect/", {}, format="json")
    assert response.status_code in {401, 403}


@pytest.mark.django_db
def test_login_and_logout_use_session(api_client, django_user_model):
    user = django_user_model.objects.create_user(username="existing", password="strong-pass-1234")
    MemberProfile.objects.create(
        user=user,
        name="Existing Member",
        phone="01033334444",
        terms_agreed_at="2026-07-12T00:00:00Z",
    )

    login = api_client.post(
        "/api/accounts/login/",
        {"username": "existing", "password": "strong-pass-1234"},
        format="json",
    )
    assert login.status_code == 200
    assert api_client.get("/api/accounts/me/").status_code == 200
    assert api_client.post("/api/accounts/logout/").status_code == 204
    assert api_client.get("/api/accounts/me/").status_code in {401, 403}


@pytest.mark.django_db
def test_member_updates_profile(api_client, django_user_model):
    user = django_user_model.objects.create_user(username="profile", email="old@example.com", password="password")
    MemberProfile.objects.create(
        user=user, name="Old", phone="01010000000", terms_agreed_at="2026-07-12T00:00:00Z"
    )
    api_client.force_login(user)

    response = api_client.patch(
        "/api/accounts/me/",
        {"email": "new@example.com", "name": "New", "phone": "01020000000", "marketing_agreed": True},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New"
    user.refresh_from_db()
    user.member_profile.refresh_from_db()
    assert user.email == "new@example.com"
    assert user.member_profile.marketing_agreed is True


@pytest.mark.django_db
def test_registration_rejects_missing_required_terms(api_client):
    payload = {**REGISTRATION, "username": "no_terms", "email": "no-terms@example.com", "phone": "01055556666", "terms_agreed": False}
    response = api_client.post("/api/accounts/register/", payload, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_registration_applies_django_password_validators(api_client):
    payload = {
        **REGISTRATION, "username": "weak_password", "email": "weak@example.com",
        "phone": "01055557777", "password": "12345678",
    }
    response = api_client.post("/api/accounts/register/", payload, format="json")
    assert response.status_code == 400
    assert "password" in response.json()


@pytest.mark.django_db
def test_member_manages_private_default_shipping_address(api_client, django_user_model):
    user = django_user_model.objects.create_user(username="address-user", password="strong-pass-1234")
    api_client.force_login(user)
    first = api_client.post(
        "/api/accounts/addresses/",
        {"label": "집", "recipient_name": "Kim", "recipient_phone": "01011110000", "postal_code": "06000", "address1": "Seoul", "address2": "101"},
        format="json",
    )
    second = api_client.post(
        "/api/accounts/addresses/",
        {"label": "회사", "recipient_name": "Kim", "recipient_phone": "01011110000", "postal_code": "04500", "address1": "Seoul Office", "is_default": True},
        format="json",
    )
    assert first.status_code == 201
    assert second.status_code == 201
    addresses = api_client.get("/api/accounts/addresses/").json()["results"]
    assert addresses[0]["label"] == "회사"
    assert addresses[0]["is_default"] is True
    assert sum(address["is_default"] for address in addresses) == 1

    cannot_unset = api_client.patch(
        f"/api/accounts/addresses/{second.json()['id']}/", {"is_default": False}, format="json"
    )
    assert cannot_unset.status_code == 400

    assert api_client.delete(f"/api/accounts/addresses/{second.json()['id']}/").status_code == 204
    remaining = api_client.get("/api/accounts/addresses/").json()["results"]
    assert remaining[0]["is_default"] is True

    other = django_user_model.objects.create_user(username="address-other", password="strong-pass-1234")
    api_client.force_login(other)
    assert api_client.get(f"/api/accounts/addresses/{first.json()['id']}/").status_code == 404


@pytest.mark.django_db
def test_registration_claims_existing_guest_cart(api_client):
    brand = Brand.objects.create(name="Cart Brand", slug="cart-brand")
    category = Category.objects.create(name="Cart Category", slug="cart-category")
    product = Product.objects.create(
        brand=brand, category=category, sabangnet_product_code="SB-CLAIM", custom_product_code="CLAIM",
        name="Claim Product", selling_price=10000, consumer_price=10000, tax_code="TAXABLE", supply_status="IN_SUPPLY",
    )
    variant = ProductVariant.objects.create(
        product=product, variant_code="CLAIM-V", option_display_name="One", stock_quantity=10, supply_status="SALE",
    )
    listing = ProductListing.objects.create(
        product=product, listing_code="CLAIM-L", status="active", display_name="Claim Product",
        slug="claim-product", selling_price_snapshot=10000, consumer_price_snapshot=10000,
    )
    listing_variant = listing.variants.create(variant=variant, status="active")
    api_client.post(
        "/api/commerce/cart/items/",
        {"listing_variant_id": listing_variant.id, "quantity": 2},
        format="json",
        HTTP_X_GUEST_KEY="claim-me",
    )

    payload = {**REGISTRATION, "username": "cart_member", "email": "cart@example.com", "phone": "01077778888"}
    registered = api_client.post(
        "/api/accounts/register/",
        payload,
        format="json",
        HTTP_X_GUEST_KEY="claim-me",
    )

    assert registered.status_code == 201
    cart = Cart.objects.get(user__username="cart_member", status=Cart.Status.ACTIVE)
    assert cart.guest_key_hash is None
    assert cart.items.get().quantity == 2

    member_cart = api_client.get("/api/commerce/cart/items/")
    assert member_cart.status_code == 200
    assert member_cart.json()["summary"]["item_count"] == 2

    order_response = api_client.post(
        "/api/commerce/orders/",
        {
            "buyer_name": "Cart Member", "buyer_phone": "01077778888", "buyer_email": "cart@example.com",
            "recipient_name": "Receiver", "recipient_phone": "01099990000", "postal_code": "06000",
            "address1": "Seoul", "address2": "Gangnam",
        },
        format="json",
    )
    assert order_response.status_code == 201
    order = Order.objects.get(order_number=order_response.json()["order_number"])
    assert order.user.username == "cart_member"
    assert order.guest_order_key_hash is None
    assert api_client.get(f"/api/commerce/orders/{order.order_number}/").status_code == 200
    mine = api_client.get("/api/commerce/orders/mine/")
    assert mine.status_code == 200
    assert mine.json()["results"][0]["order_number"] == order.order_number
