from django.db import transaction
from django.utils.text import slugify

from .models import ProductListing, ProductListingVariant


MAIN_MALL_CHANNEL = "main_mall"
SABANGNET_PRICE_SOURCE = "sabangnet"


class ListingActivationError(Exception):
    pass


def sabangnet_listing_code(product):
    return f"SABANGNET-{product.pk}"


def sabangnet_listing_slug(product):
    suffix = f"-{product.pk}"
    base = slugify(product.name) or "product"
    return f"{base[: 260 - len(suffix)]}{suffix}"


def ensure_sabangnet_draft_listing(product):
    listing = product.listings.filter(
        sales_channel=MAIN_MALL_CHANNEL,
        price_source=SABANGNET_PRICE_SOURCE,
    ).order_by("pk").first()
    if listing is not None:
        return listing, False

    # A manually curated listing for the main mall takes precedence. Creating a
    # second draft would make the administrator choose between duplicate rows.
    if product.listings.filter(sales_channel=MAIN_MALL_CHANNEL).exists():
        return None, False

    return ProductListing.objects.create(
        product=product,
        listing_code=sabangnet_listing_code(product),
        sales_channel=MAIN_MALL_CHANNEL,
        status=ProductListing.Status.DRAFT,
        display_name=product.name,
        slug=sabangnet_listing_slug(product),
        listing_detail_html=product.detail_html,
        seo_title=product.name,
        consumer_price_snapshot=product.consumer_price,
        selling_price_snapshot=product.selling_price,
        price_source=SABANGNET_PRICE_SOURCE,
        search_keywords=product.product_tags,
    ), True


def listing_variant_public_status(variant):
    if variant.available_quantity > 0 and variant.supply_status == "SALE":
        return ProductListingVariant.Status.ACTIVE
    return ProductListingVariant.Status.SOLD_OUT


def sync_sabangnet_listings(product, variants):
    ensure_sabangnet_draft_listing(product)
    listings = product.listings.filter(price_source=SABANGNET_PRICE_SOURCE)
    for listing in listings:
        listing.consumer_price_snapshot = product.consumer_price
        listing.selling_price_snapshot = product.selling_price
        listing.save(update_fields=["consumer_price_snapshot", "selling_price_snapshot", "updated_at"])
        for index, variant in enumerate(variants):
            status = (
                ProductListingVariant.Status.DRAFT
                if listing.status == ProductListing.Status.DRAFT
                else listing_variant_public_status(variant)
            )
            ProductListingVariant.objects.update_or_create(
                listing=listing,
                variant=variant,
                defaults={
                    "status": status,
                    "additional_amount_snapshot": variant.additional_amount,
                    "sort_order": index,
                },
            )


@transaction.atomic
def activate_draft_listing(listing_id):
    listing = (
        ProductListing.objects.select_for_update()
        .select_related("product")
        .get(pk=listing_id)
    )
    if listing.status != ProductListing.Status.DRAFT:
        raise ListingActivationError("작성 중인 판매 상품만 판매 중으로 전환할 수 있습니다.")
    if not listing.display_name.strip() or not listing.slug.strip():
        raise ListingActivationError("표시 상품명과 URL 식별자를 입력해 주세요.")
    if listing.selling_price_snapshot <= 0:
        raise ListingActivationError("판매가가 0원인 상품은 판매 중으로 전환할 수 없습니다.")
    if ProductListing.objects.exclude(pk=listing.pk).filter(
        product=listing.product,
        sales_channel=listing.sales_channel,
        status=ProductListing.Status.ACTIVE,
    ).exists():
        raise ListingActivationError("같은 상품과 판매 채널에 이미 판매 중인 상품이 있습니다.")
    if ProductListing.objects.exclude(pk=listing.pk).filter(
        slug=listing.slug,
        status__in=[ProductListing.Status.ACTIVE, ProductListing.Status.SCHEDULED],
    ).exists():
        raise ListingActivationError("같은 URL 식별자를 사용 중인 공개 상품이 있습니다.")

    listing_variants = list(
        listing.variants.select_for_update().select_related("variant").order_by("pk")
    )
    if not listing_variants:
        raise ListingActivationError("판매 상품 옵션이 하나 이상 필요합니다.")

    for listing_variant in listing_variants:
        listing_variant.status = listing_variant_public_status(listing_variant.variant)
        listing_variant.save(update_fields=["status", "updated_at"])

    listing.status = ProductListing.Status.ACTIVE
    listing.save(update_fields=["status", "updated_at"])
    return listing
