import pytest

from catalog.models import Product, ProductImage, ProductListing, ProductSyncSnapshot
from integrations.sabangnet_products import sync_product


PRODUCT_PAYLOAD = {
    "productCode": "SB-SYNC-1000",
    "customProductCode": "SEQ-SYNC-1000",
    "productName": "Synced Jacket",
    "engProductName": "Synced Jacket",
    "brandName": "Sync Brand",
    "manufacturerName": "Sync Factory",
    "consumerPrice": 129000,
    "sellingPrice": 99000,
    "costPrice": 50000,
    "taxCode": "TAXABLE",
    "productSupplyStatusCode": "IN_SUPPLY",
    "productDetailDescription": "<p>사방넷 상세 설명</p>",
    "productTag": "jacket,black",
    "optionInfo": {
        "options": [
            {
                "optionName": "색상/사이즈",
                "optionDetailName": "Black / M",
                "variantCode": "SEQ-SYNC-1000-BLK-M",
                "barcode": "880000007777",
                "stockQuantity": 8,
                "additionalAmount": 1000,
                "optionSupplyStatusCode": "SALE",
            }
        ]
    },
    "imageInfo": [
        {"imageSrno": "1", "imagePath": "https://example.com/sync-main.jpg"},
        {"imageSrno": "2", "imagePath": "https://example.com/sync-sub.jpg"},
    ],
}


@pytest.mark.django_db
def test_sabangnet_product_sync_creates_product_options_images_and_snapshot():
    product = sync_product(PRODUCT_PAYLOAD)

    assert product.name == "Synced Jacket"
    assert product.custom_product_code == "SEQ-SYNC-1000"
    assert product.brand.name == "Sync Brand"
    assert product.selling_price == 99000
    assert product.detail_html == "<p>사방넷 상세 설명</p>"
    variant = product.variants.get()
    assert variant.option_display_name == "색상/사이즈 / Black / M"
    assert variant.stock_quantity == 8
    assert variant.additional_amount == 1000
    images = list(product.images.all())
    assert len(images) == 2
    assert images[0].is_primary is True
    assert images[0].image_url == "https://example.com/sync-main.jpg"
    assert ProductSyncSnapshot.objects.get(product=product).status == ProductSyncSnapshot.Status.CREATED


@pytest.mark.django_db
def test_resync_updates_sabangnet_listing_price_options_and_images():
    product = sync_product(PRODUCT_PAYLOAD)
    listing = ProductListing.objects.create(
        product=product,
        listing_code="SYNC-LISTING",
        status="active",
        display_name="Synced Jacket",
        slug="synced-jacket",
        consumer_price_snapshot=129000,
        selling_price_snapshot=99000,
        price_source="sabangnet",
    )
    changed = {
        **PRODUCT_PAYLOAD,
        "sellingPrice": 89000,
        "optionInfo": {"options": [{**PRODUCT_PAYLOAD["optionInfo"]["options"][0], "stockQuantity": 0}]},
        "imageInfo": [{"imageSrno": "3", "imagePath": "https://example.com/new-main.jpg"}],
    }

    synced = sync_product(changed)

    listing.refresh_from_db()
    synced.variants.get().refresh_from_db()
    assert listing.selling_price_snapshot == 89000
    assert listing.variants.get().status == "sold_out"
    assert list(synced.images.values_list("image_url", flat=True)) == ["https://example.com/new-main.jpg"]
    assert ProductSyncSnapshot.objects.filter(product=synced, status=ProductSyncSnapshot.Status.UPDATED).exists()


@pytest.mark.django_db
def test_catalog_api_exposes_primary_sabangnet_image(api_client):
    product = sync_product(PRODUCT_PAYLOAD)
    ProductListing.objects.create(
        product=product,
        listing_code="SYNC-PUBLIC",
        status="active",
        display_name="Synced Jacket",
        slug="synced-jacket-public",
        consumer_price_snapshot=129000,
        selling_price_snapshot=99000,
        price_source="sabangnet",
    )
    response = api_client.get("/api/catalog/listings/")
    images = response.json()["results"][0]["product"]["images"]
    assert images[0]["is_primary"] is True
    assert images[0]["image_url"] == "https://example.com/sync-main.jpg"
