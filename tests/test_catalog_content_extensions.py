import pytest
from django.utils import timezone

from catalog.models import ProductAttribute, ProductInformationNotice, SearchKeyword
from content.models import FAQ, Lookbook, LookbookImage, Notice, PolicyPage, Promotion, PromotionListing
from integrations.sabangnet_categories import sync_categories
from integrations.sabangnet_products import sync_product


@pytest.mark.django_db
def test_sabangnet_category_paths_sync_parent_relationships():
    payload = {"categories": [{"category": [
        {"code": "01", "name": "의류", "level": 1, "sortSrno": 1, "useYn": "Y"},
        {"code": "0101", "name": "수영복", "level": 2, "sortSrno": 2, "useYn": "Y"},
    ]}]}

    categories = sync_categories(payload)

    assert len(categories) == 2
    child = next(item for item in categories if item.sabangnet_code == "0101")
    assert child.parent.sabangnet_code == "01"
    assert child.level == 2


@pytest.mark.django_db
def test_product_sync_stores_attributes_notice_and_category():
    product = sync_product({
        "productCode": "SB-EXT-1", "productName": "Swimsuit", "categoryCode": "SWIM",
        "categoryName": "Swimwear", "sellingPrice": 50000, "consumerPrice": 60000,
        "productSupplyStatusCode": "SALE",
        "attributes": [{"name": "컬러", "value": "블랙"}],
        "productInfoNotice": {"type": "의류", "fields": {"소재": "나일론", "세탁방법": "단독세탁"}},
    })

    assert product.category.sabangnet_code == "SWIM"
    assert ProductAttribute.objects.filter(product=product, name="컬러", value="블랙").exists()
    assert ProductInformationNotice.objects.get(product=product).fields["소재"] == "나일론"


@pytest.mark.django_db
def test_filter_and_search_keyword_apis(api_client, listing_variant):
    ProductAttribute.objects.create(product=listing_variant.listing.product, name="컬러", value="White")

    filtered = api_client.get("/api/catalog/listings/?attribute=컬러:White&q=Panel")
    filters = api_client.get("/api/catalog/filters/")
    keywords = api_client.get("/api/catalog/search-keywords/")

    assert filtered.status_code == 200
    assert filtered.json()["count"] == 1
    assert filters.json() == [{"name": "컬러", "values": ["White"]}]
    assert SearchKeyword.objects.get(keyword="Panel").search_count == 1
    assert keywords.json()["popular"][0]["keyword"] == "Panel"


@pytest.mark.django_db
def test_public_content_endpoints(api_client, listing_variant):
    now = timezone.now()
    promotion = Promotion.objects.create(title="Summer", slug="summer", is_visible=True)
    PromotionListing.objects.create(promotion=promotion, listing=listing_variant.listing)
    lookbook = Lookbook.objects.create(title="Resort", slug="resort", is_visible=True)
    LookbookImage.objects.create(lookbook=lookbook, image_url="https://example.com/look.jpg")
    Notice.objects.create(title="배송 안내", content="내용", published_at=now)
    FAQ.objects.create(category="배송", question="언제 오나요?", answer="출고 후 1~2일")
    PolicyPage.objects.create(policy_type="returns", title="교환·반품", content="정책", version="1")

    assert api_client.get("/api/content/promotions/summer/").json()["title"] == "Summer"
    assert api_client.get("/api/content/lookbooks/resort/").json()["images"][0]["image_url"].endswith("look.jpg")
    assert api_client.get("/api/content/notices/").json()[0]["title"] == "배송 안내"
    assert api_client.get("/api/content/faqs/?category=배송").json()[0]["category"] == "배송"
    assert api_client.get("/api/content/policies/returns/").json()["version"] == "1"
