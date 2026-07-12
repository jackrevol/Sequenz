import hashlib
import json
from urllib import error, parse, request

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from catalog.models import Brand, Product, ProductImage, ProductListingVariant, ProductSyncSnapshot, ProductVariant


class SabangnetProductError(Exception):
    pass


class SabangnetProductClient:
    def __init__(self, base_url=None, bearer_token=None, service_account_id=None, timeout=15):
        self.base_url = base_url or settings.SABANGNET_API_BASE_URL
        self.bearer_token = bearer_token or settings.SABANGNET_BEARER_TOKEN
        self.service_account_id = service_account_id or settings.SABANGNET_SVC_ACCOUNT_ID
        self.timeout = timeout

    def fetch_product(self, product_code=None, custom_product_code=None):
        if not self.base_url or not self.bearer_token or not self.service_account_id:
            raise SabangnetProductError("사방넷 상품조회 API 환경변수가 설정되지 않았습니다.")
        params = {}
        if custom_product_code:
            params["customProductCode"] = custom_product_code
        elif product_code:
            params["productCode"] = product_code
        else:
            raise SabangnetProductError("상품코드 또는 자체상품코드가 필요합니다.")
        url = f"{self.base_url.rstrip('/')}/v3/sb/product?{parse.urlencode(params)}"
        http_request = request.Request(
            url,
            headers={"Authorization": f"Bearer {self.bearer_token}", "X-Svc-Acnt-Id": self.service_account_id},
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode())
        except error.HTTPError as exc:
            raise SabangnetProductError(f"사방넷 상품조회가 HTTP {exc.code}로 실패했습니다.") from exc
        except (error.URLError, TimeoutError, ValueError) as exc:
            raise SabangnetProductError("사방넷 상품조회 응답을 처리하지 못했습니다.") from exc
        product_data = _extract_product(payload)
        if not product_data:
            raise SabangnetProductError("사방넷 상품조회 결과가 비어 있습니다.")
        return product_data


@transaction.atomic
def sync_product(product_data):
    product_code = str(_value(product_data, "productCode", "PRODUCT_CODE", default="")).strip()
    if not product_code:
        raise SabangnetProductError("productCode가 없는 상품은 동기화할 수 없습니다.")
    custom_code = _nullable_text(_value(product_data, "customProductCode", "CUSTOM_PRODUCT_CODE"))
    brand = _sync_brand(_value(product_data, "brandName", "BRAND_NAME"))
    defaults = {
        "custom_product_code": custom_code,
        "brand": brand,
        "name": str(_value(product_data, "productName", "PRODUCT_NAME", default=product_code)),
        "english_name": str(_value(product_data, "engProductName", "ENG_PRODUCT_NAME", default="")),
        "model_name": str(_value(product_data, "modelName", "MODEL_NAME", default="")),
        "manufacturer_name": str(_value(product_data, "manufacturerName", "MANUFACTURER_NAME", default="")),
        "consumer_price": _integer(_value(product_data, "consumerPrice", "CONSUMER_PRICE")),
        "selling_price": _integer(_value(product_data, "sellingPrice", "SELLING_PRICE")),
        "cost_price": _optional_integer(_value(product_data, "costPrice", "COST_PRICE")),
        "tax_code": str(_value(product_data, "taxCode", "TAX_CODE", default="TAXABLE")),
        "supply_status": str(_value(product_data, "productSupplyStatusCode", "SUPPLY_STATUS", default="")),
        "target_code": str(_value(product_data, "productTargetCode", default="")),
        "season_code": str(_value(product_data, "seasonCode", default="")),
        "product_tags": str(_value(product_data, "productTag", default="")),
        "detail_html": str(_value(product_data, "productDetailDescription", default="")),
        "synced_at": timezone.now(),
        "raw_sabangnet_payload": _safe_payload_summary(product_data),
    }
    existing = Product.objects.select_for_update().filter(sabangnet_product_code=product_code).first()
    changes = _changed_fields(existing, defaults) if existing else {
        key: {"to": _snapshot_value(value)} for key, value in defaults.items() if key != "raw_sabangnet_payload"
    }
    product, created = Product.objects.update_or_create(sabangnet_product_code=product_code, defaults=defaults)
    variants = _sync_variants(product, product_data)
    images = _sync_images(product, product_data)
    _sync_listings(product, variants)
    ProductSyncSnapshot.objects.create(
        product=product,
        sabangnet_product_code=product_code,
        status=ProductSyncSnapshot.Status.CREATED if created else ProductSyncSnapshot.Status.UPDATED,
        field_changes=changes,
    )
    return product


def sync_product_safely(product_data):
    try:
        return sync_product(product_data)
    except Exception as exc:
        product_code = str(_value(product_data, "productCode", "PRODUCT_CODE", default=""))[:80]
        ProductSyncSnapshot.objects.create(
            sabangnet_product_code=product_code,
            status=ProductSyncSnapshot.Status.FAILED,
            error_message=str(exc)[:2000],
        )
        raise


def _sync_brand(name):
    name = str(name or "").strip()
    if not name:
        return None
    existing = Brand.objects.filter(name=name).first()
    if existing:
        return existing
    base = slugify(name, allow_unicode=True) or f"brand-{hashlib.sha1(name.encode()).hexdigest()[:8]}"
    slug = base
    suffix = 1
    while Brand.objects.filter(slug=slug).exists():
        suffix += 1
        slug = f"{base}-{suffix}"
    return Brand.objects.create(name=name, slug=slug)


def _sync_variants(product, payload):
    option_info = _value(payload, "optionInfo", default={}) or {}
    options = _value(option_info, "options", default=[]) or []
    synced = []
    for index, option in enumerate(options):
        name = str(_value(option, "optionDisplayName", default="")).strip()
        if not name:
            name = " / ".join(
                part for part in [str(_value(option, "optionName", default="")).strip(), str(_value(option, "optionDetailName", default="")).strip()] if part
            ) or f"옵션 {index + 1}"
        variant_code = _nullable_text(_value(option, "variantCode", "optionCode", "skuCode"))
        variant, _ = ProductVariant.objects.update_or_create(
            product=product,
            option_display_name=name,
            defaults={
                "variant_code": variant_code,
                "sabangnet_option_id": str(_value(option, "optionSrno", "optionId", default="")),
                "barcode": str(_value(option, "barcode", "barcodeNo", default="")),
                "additional_amount": _integer(_value(option, "additionalAmount", "optionPrice")),
                "stock_quantity": _integer(_value(option, "stockQuantity", "stockQty")),
                "supply_status": str(_value(option, "optionSupplyStatusCode", "supplyStatus", default="SALE")),
                "synced_at": timezone.now(),
            },
        )
        synced.append(variant)
    return synced


def _sync_images(product, payload):
    image_rows = _value(payload, "imageInfo", default=[]) or []
    urls = []
    has_admin_primary = product.images.filter(source=ProductImage.Source.ADMIN, is_primary=True).exists()
    product.images.filter(source=ProductImage.Source.SABANGNET, is_primary=True).update(is_primary=False)
    synced = []
    for index, image in enumerate(image_rows):
        url = str(_value(image, "imagePath", "imageUrl", default="")).strip()
        if not url:
            continue
        urls.append(url)
        serial = str(_value(image, "imageSrno", default=""))
        lookup = {"product": product, "source": ProductImage.Source.SABANGNET}
        lookup["sabangnet_image_srno" if serial else "image_url"] = serial or url
        image_obj, _ = ProductImage.objects.update_or_create(
            **lookup,
            defaults={
                "image_url": url,
                "alt_text": product.name,
                "sort_order": index,
                "is_primary": index == 0 and not has_admin_primary,
            },
        )
        synced.append(image_obj)
    product.images.filter(source=ProductImage.Source.SABANGNET).exclude(image_url__in=urls).delete()
    return synced


def _sync_listings(product, variants):
    for listing in product.listings.filter(price_source="sabangnet"):
        listing.consumer_price_snapshot = product.consumer_price
        listing.selling_price_snapshot = product.selling_price
        listing.save(update_fields=["consumer_price_snapshot", "selling_price_snapshot", "updated_at"])
        for index, variant in enumerate(variants):
            ProductListingVariant.objects.update_or_create(
                listing=listing,
                variant=variant,
                defaults={
                    "status": ProductListingVariant.Status.ACTIVE if variant.stock_quantity > 0 and variant.supply_status == "SALE" else ProductListingVariant.Status.SOLD_OUT,
                    "additional_amount_snapshot": variant.additional_amount,
                    "sort_order": index,
                },
            )


def _extract_product(payload):
    if isinstance(payload, list):
        return payload[0] if payload else None
    if not isinstance(payload, dict):
        return None
    if _value(payload, "productCode", "PRODUCT_CODE"):
        return payload
    for key in ("product", "data", "result", "items", "products"):
        nested = payload.get(key)
        result = _extract_product(nested)
        if result:
            return result
    return None


def _value(payload, *keys, default=None):
    if not isinstance(payload, dict):
        return default
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return default


def _integer(value):
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _optional_integer(value):
    return None if value in (None, "") else _integer(value)


def _nullable_text(value):
    text = str(value or "").strip()
    return text or None


def _safe_payload_summary(payload):
    excluded = {"token", "accessToken", "secret", "password"}
    return {key: value for key, value in payload.items() if key not in excluded}


def _changed_fields(existing, defaults):
    changes = {}
    for key, new_value in defaults.items():
        if key == "raw_sabangnet_payload":
            continue
        old_value = getattr(existing, key)
        if old_value != new_value:
            changes[key] = {"from": _snapshot_value(old_value), "to": _snapshot_value(new_value)}
    return changes


def _snapshot_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "pk"):
        return {"id": value.pk, "label": str(value)}
    return str(value)
