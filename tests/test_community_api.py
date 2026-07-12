import pytest

from accounts.models import MemberProfile
from catalog.models import Brand, Category, Product, ProductListing
from commerce.models import Order, OrderItem
from community.models import CustomerInquiry, ProductReview


@pytest.fixture
def member_purchase(db, django_user_model):
    user = django_user_model.objects.create_user(username="reviewer", password="strong-pass-1234")
    MemberProfile.objects.create(user=user, name="Reviewer", phone="01012121212", terms_agreed_at="2026-07-12T00:00:00Z")
    brand = Brand.objects.create(name="Review Brand", slug="review-brand")
    category = Category.objects.create(name="Review Category", slug="review-category")
    product = Product.objects.create(
        brand=brand, category=category, sabangnet_product_code="SB-REVIEW", custom_product_code="REVIEW",
        name="Review Product", selling_price=30000, consumer_price=30000, tax_code="TAXABLE", supply_status="IN_SUPPLY",
    )
    listing = ProductListing.objects.create(
        product=product, listing_code="REVIEW-L", status="active", display_name="Review Product",
        slug="review-product", selling_price_snapshot=30000, consumer_price_snapshot=30000,
    )
    order = Order.objects.create(
        order_number="SEQ-REVIEW-ORDER", user=user, status=Order.Status.PAID,
        fulfillment_status=Order.FulfillmentStatus.DELIVERED,
        buyer_name="Reviewer", buyer_phone="01012121212", recipient_name="Reviewer",
        recipient_phone="01012121212", postal_code="06000", address1="Seoul",
        items_subtotal=30000, payment_amount=30000,
    )
    item = OrderItem.objects.create(
        order=order, listing=listing, listing_code_snapshot=listing.listing_code,
        listing_name_snapshot=listing.display_name, listing_price_source_snapshot="admin",
        product_name_snapshot=product.name, sabangnet_product_code=product.sabangnet_product_code,
        custom_product_code=product.custom_product_code, ordered_quantity=1, unit_price=30000, line_total=30000,
    )
    return user, order, item, listing


@pytest.mark.django_db
def test_paid_member_can_create_one_review_and_public_can_read_it(api_client, member_purchase):
    user, _, item, listing = member_purchase
    api_client.force_login(user)
    created = api_client.post(
        "/api/community/reviews/",
        {"order_item_id": item.id, "rating": 5, "title": "좋아요", "body": "만족합니다."},
        format="json",
    )
    duplicate = api_client.post(
        "/api/community/reviews/",
        {"order_item_id": item.id, "rating": 4, "body": "두 번째"},
        format="json",
    )
    api_client.logout()
    public = api_client.get(f"/api/community/reviews/listing/{listing.id}/")

    assert created.status_code == 201
    assert duplicate.status_code == 400
    assert public.json()["summary"] == {"count": 1, "average_rating": 5.0}
    assert public.json()["results"][0]["reviewer_name"].startswith("R")
    assert ProductReview.objects.count() == 1
    item.refresh_from_db()
    assert item.review_status == "written"


@pytest.mark.django_db
def test_inquiry_is_private_to_member(api_client, member_purchase, django_user_model):
    user, order, _, _ = member_purchase
    api_client.force_login(user)
    created = api_client.post(
        "/api/community/inquiries/",
        {"order_id": order.id, "category": "delivery", "subject": "배송 문의", "body": "언제 출발하나요?"},
        format="json",
    )
    assert created.status_code == 201
    assert api_client.get("/api/community/inquiries/").json()["results"][0]["subject"] == "배송 문의"

    other = django_user_model.objects.create_user(username="other", password="strong-pass-1234")
    api_client.force_login(other)
    assert api_client.get(f"/api/community/inquiries/{created.json()['id']}/").status_code == 404
    assert CustomerInquiry.objects.count() == 1
