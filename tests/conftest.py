import pytest
from rest_framework.test import APIClient

from catalog.models import Brand, Category, Product, ProductListing, ProductVariant


@pytest.fixture
def api_client():
    return APIClient()


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
