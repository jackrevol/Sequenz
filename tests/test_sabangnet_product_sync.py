import pytest
from copy import deepcopy
from unittest.mock import patch
from django.core.management import call_command

from catalog.models import Category, Product, ProductImage, ProductListing, ProductListingVariant, ProductSyncSnapshot
from integrations.models import ExternalApiLog, IntegrationJob, OperationsAuditLog
from integrations.sabangnet_products import SabangnetProductError
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
    listing = product.listings.get()
    assert listing.status == ProductListing.Status.DRAFT
    assert listing.display_name == product.name
    assert listing.selling_price_snapshot == product.selling_price
    assert listing.variants.get().status == ProductListingVariant.Status.DRAFT
    assert ProductSyncSnapshot.objects.get(product=product).status == ProductSyncSnapshot.Status.CREATED


@pytest.mark.django_db
def test_resync_updates_sabangnet_listing_price_options_and_images():
    product = sync_product(PRODUCT_PAYLOAD)
    listing = product.listings.get()
    listing.status = ProductListing.Status.ACTIVE
    listing.save(update_fields=["status", "updated_at"])
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
def test_product_without_options_gets_safe_draft_default_option():
    payload = {**PRODUCT_PAYLOAD, "productCode": "SB-NO-OPTION", "customProductCode": "NO-OPTION"}
    payload.pop("optionInfo")

    product = sync_product(payload)

    variant = product.variants.get()
    listing = product.listings.get()
    assert variant.option_display_name == "기본 옵션"
    assert variant.stock_quantity == 0
    assert listing.status == ProductListing.Status.DRAFT
    assert listing.variants.get().status == ProductListingVariant.Status.DRAFT


@pytest.mark.django_db
def test_admin_can_bulk_activate_reviewed_draft_listings(client, django_user_model):
    admin = django_user_model.objects.create_superuser("listing-admin", "listing@example.com", "password")
    client.force_login(admin)
    product = sync_product(PRODUCT_PAYLOAD)
    listing = product.listings.get()

    response = client.post(
        "/admin/catalog/productlisting/",
        {"action": "activate_selected_listings", "_selected_action": [listing.pk]},
        follow=True,
    )

    listing.refresh_from_db()
    assert response.status_code == 200
    assert listing.status == ProductListing.Status.ACTIVE
    assert listing.variants.get().status == ProductListingVariant.Status.ACTIVE


@pytest.mark.django_db
def test_admin_does_not_activate_zero_price_draft_listing(client, django_user_model):
    admin = django_user_model.objects.create_superuser("safe-listing-admin", "safe-listing@example.com", "password")
    client.force_login(admin)
    product = sync_product({**PRODUCT_PAYLOAD, "productCode": "SB-ZERO", "customProductCode": "ZERO", "sellingPrice": 0})
    listing = product.listings.get()

    response = client.post(
        "/admin/catalog/productlisting/",
        {"action": "activate_selected_listings", "_selected_action": [listing.pk]},
        follow=True,
    )

    listing.refresh_from_db()
    assert listing.status == ProductListing.Status.DRAFT
    assert "판매가가 0원인 상품" in response.content.decode()


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


@pytest.mark.django_db
def test_sandbox_product_uses_deepest_my_category_and_excludes_service_account_from_snapshot():
    category = Category.objects.create(name="Tops", slug="tops", sabangnet_code="010101", level=3)
    payload = {
        **PRODUCT_PAYLOAD,
        "productCode": "SB-SANDBOX-1",
        "myCategoryCodeL": "01",
        "myCategoryCodeM": "0101",
        "myCategoryCodeS": "010101",
        "svcAcntId": "must-not-be-persisted",
    }

    product = sync_product(payload)

    assert product.category == category
    assert "svcAcntId" not in product.raw_sabangnet_payload


@pytest.mark.django_db
def test_admin_can_manually_sync_multiple_sabangnet_products(client, django_user_model):
    admin = django_user_model.objects.create_superuser("product-sync-admin", "sync@example.com", "password")
    client.force_login(admin)

    def fetch_product(**kwargs):
        code = kwargs["product_code"]
        payload = deepcopy(PRODUCT_PAYLOAD)
        payload.update({"productCode": code, "customProductCode": f"CUSTOM-{code}"})
        payload["optionInfo"]["options"][0].update({"variantCode": f"VARIANT-{code}", "barcode": f"BARCODE-{code}"})
        return payload

    response = client.post(
        "/admin/catalog/product/sabangnet-sync/",
        {"identifier_type": "product_code", "mode": "codes", "codes": "SB-100\nSB-200"},
    )

    assert response.status_code == 302
    job = IntegrationJob.objects.get(job_type="manual_product_sync")
    assert job.status == IntegrationJob.Status.QUEUED
    assert job.request_summary["codes"] == ["SB-100", "SB-200"]
    assert not Product.objects.exists()

    with patch("integrations.sabangnet_product_jobs.SabangnetProductClient.fetch_product", side_effect=fetch_product):
        call_command("process_integration_jobs")

    job.refresh_from_db()
    assert set(Product.objects.values_list("sabangnet_product_code", flat=True)) == {"SB-100", "SB-200"}
    assert job.status == IntegrationJob.Status.SUCCEEDED
    assert job.success_count == 2
    assert job.failure_count == 0
    assert OperationsAuditLog.objects.get().action == "sabangnet_product_manual_sync"


@pytest.mark.django_db
def test_admin_manual_product_sync_keeps_successes_and_logs_failures(client, django_user_model):
    admin = django_user_model.objects.create_superuser("partial-sync-admin", "partial@example.com", "password")
    client.force_login(admin)

    def fetch_product(**kwargs):
        code = kwargs["product_code"]
        if code == "SB-BAD":
            raise SabangnetProductError("상품을 찾을 수 없습니다.")
        return {**PRODUCT_PAYLOAD, "productCode": code, "customProductCode": f"CUSTOM-{code}"}

    response = client.post(
        "/admin/catalog/product/sabangnet-sync/",
        {"identifier_type": "product_code", "mode": "codes", "codes": "SB-GOOD, SB-BAD"},
    )

    assert response.status_code == 302
    job = IntegrationJob.objects.get(job_type="manual_product_sync")

    with patch("integrations.sabangnet_product_jobs.SabangnetProductClient.fetch_product", side_effect=fetch_product):
        call_command("process_integration_jobs")

    job.refresh_from_db()
    assert Product.objects.filter(sabangnet_product_code="SB-GOOD").exists()
    assert job.status == IntegrationJob.Status.PARTIAL
    assert job.success_count == 1
    assert job.failure_count == 1
    error = ExternalApiLog.objects.get(job=job)
    assert error.request_summary["product_identifier"] == "SB-BAD"
    assert "찾을 수 없습니다" in error.error_message


@pytest.mark.django_db
def test_admin_queues_166_products_without_syncing_in_web_request(client, django_user_model):
    admin = django_user_model.objects.create_superuser("bulk-sync-admin", "bulk@example.com", "password")
    client.force_login(admin)
    codes = [f"SB-{number:04d}" for number in range(166)]

    with patch("integrations.sabangnet_product_jobs.SabangnetProductClient.fetch_product") as fetch:
        response = client.post(
            "/admin/catalog/product/sabangnet-sync/",
            {"identifier_type": "product_code", "mode": "codes", "codes": "\n".join(codes)},
        )

    assert response.status_code == 302
    assert not fetch.called
    job = IntegrationJob.objects.get(job_type="manual_product_sync")
    assert job.status == IntegrationJob.Status.QUEUED
    assert job.total_count == 166
    assert job.request_summary["codes"] == codes
