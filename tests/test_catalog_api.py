import pytest

from catalog.models import Brand, Category, Product, ProductListing, ProductVariant


@pytest.fixture
def brand(db):
    return Brand.objects.create(name="Sequenz", slug="sequenz", sort_order=1)


@pytest.fixture
def category(db):
    return Category.objects.create(name="Swimwear", slug="swimwear", level=1, sort_order=1)


@pytest.fixture
def product(db, brand, category):
    return Product.objects.create(
        brand=brand,
        category=category,
        sabangnet_product_code="SB-P-1000",
        custom_product_code="SEQ-P-1000",
        name="Archive Swimsuit",
        consumer_price=129000,
        selling_price=99000,
        tax_code="TAXABLE",
        supply_status="IN_SUPPLY",
    )


@pytest.fixture
def variant(db, product):
    return ProductVariant.objects.create(
        product=product,
        variant_code="SEQ-P-1000-BLK-M",
        barcode="880000000001",
        option_display_name="Black / M",
        additional_amount=0,
        stock_quantity=7,
        safety_stock_quantity=1,
        supply_status="SALE",
    )


@pytest.fixture
def listing(db, product, variant):
    listing = ProductListing.objects.create(
        product=product,
        listing_code="LIST-1000",
        sales_channel="main_mall",
        status="active",
        display_name="Archive Swimsuit",
        slug="archive-swimsuit",
        consumer_price_snapshot=129000,
        selling_price_snapshot=99000,
        price_source="sabangnet",
        search_keywords="swimsuit,black",
    )
    listing.variants.create(
        variant=variant,
        status="active",
        additional_amount_snapshot=0,
        stock_display_policy="show",
        sort_order=1,
    )
    return listing


@pytest.mark.django_db
def test_active_listing_list_returns_customer_facing_product(api_client, listing):
    response = api_client.get("/api/catalog/listings/")

    assert response.status_code == 200
    assert response.json()["results"][0]["display_name"] == listing.display_name
    assert response.json()["results"][0]["product"]["sabangnet_product_code"] == "SB-P-1000"
    assert response.json()["results"][0]["variants"][0]["option_display_name"] == "Black / M"


@pytest.mark.django_db
def test_paused_listing_is_not_public(api_client, listing):
    listing.status = "paused"
    listing.save(update_fields=["status"])

    response = api_client.get("/api/catalog/listings/")

    assert response.status_code == 200
    assert response.json()["results"] == []
