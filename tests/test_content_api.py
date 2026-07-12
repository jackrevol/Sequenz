from datetime import timedelta

import pytest
from django.utils import timezone

from catalog.models import Brand, Category, Product, ProductListing, ProductVariant
from content.models import CollectionListing, EditorialCollection, HomeBanner


@pytest.mark.django_db
def test_content_api_returns_visible_banner_and_collection(api_client):
    HomeBanner.objects.create(
        title="Summer Sequence",
        subtitle="A new rhythm",
        media_url="https://example.com/banner.jpg",
        link_type=HomeBanner.LinkType.EXTERNAL,
        link_url="https://example.com/summer",
    )
    HomeBanner.objects.create(
        title="Expired",
        media_url="https://example.com/expired.jpg",
        ends_at=timezone.now() - timedelta(days=1),
    )
    brand = Brand.objects.create(name="Content Brand", slug="content-brand")
    category = Category.objects.create(name="Content Category", slug="content-category")
    product = Product.objects.create(
        brand=brand, category=category, sabangnet_product_code="SB-CONTENT", custom_product_code="CONTENT",
        name="Content Product", selling_price=50000, consumer_price=60000, tax_code="TAXABLE", supply_status="IN_SUPPLY",
    )
    variant = ProductVariant.objects.create(
        product=product, variant_code="CONTENT-V", option_display_name="Default", stock_quantity=3, supply_status="SALE",
    )
    listing = ProductListing.objects.create(
        product=product, listing_code="CONTENT-L", status="active", display_name="Content Product",
        slug="content-product", selling_price_snapshot=50000, consumer_price_snapshot=60000,
    )
    listing.variants.create(variant=variant, status="active")
    collection = EditorialCollection.objects.create(title="Summer Edit", slug="summer-edit")
    CollectionListing.objects.create(collection=collection, listing=listing)

    banners = api_client.get("/api/content/banners/")
    collections = api_client.get("/api/content/collections/")

    assert banners.status_code == 200
    assert [banner["title"] for banner in banners.json()] == ["Summer Sequence"]
    assert collections.status_code == 200
    assert collections.json()[0]["slug"] == "summer-edit"
    assert collections.json()[0]["listings"][0]["display_name"] == "Content Product"


@pytest.mark.django_db
def test_hidden_collection_is_not_public(api_client):
    EditorialCollection.objects.create(title="Hidden", slug="hidden", is_visible=False)
    assert api_client.get("/api/content/collections/").json() == []
