import hashlib

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from catalog.listings import sync_sabangnet_listings
from catalog.models import Brand, Category, Product, ProductAttribute, ProductImage, ProductInformationNotice, ProductSyncSnapshot, ProductVariant
from integrations.sabangnet_client import SabangnetApiClient, SabangnetApiError


class SabangnetProductError(Exception):
    pass


class SabangnetProductClient:
    def __init__(self, base_url=None, bearer_token=None, service_account_id=None, timeout=None, api_client=None):
        self.api_client = api_client or SabangnetApiClient(
            base_url=base_url,
            bearer_token=bearer_token,
            service_account_id=service_account_id,
            timeout=timeout,
        )

    def fetch_product(self, product_code=None, custom_product_code=None):
        params = {}
        if custom_product_code:
            params["customProductCode"] = custom_product_code
        elif product_code:
            params["productCode"] = product_code
        else:
            raise SabangnetProductError("상품코드 또는 자체상품코드가 필요합니다.")
        try:
            payload = self.api_client.request_json("GET", "/product", query=params)
        except SabangnetApiError as exc:
            raise SabangnetProductError(str(exc)) from exc
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
    category = _sync_product_category(product_data)
    defaults = {
        "custom_product_code": custom_code,
        "brand": brand,
        "category": category,
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
    _sync_attributes(product, product_data)
    _sync_information_notice(product, product_data)
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


def sync_order_products(order, client=None):
    client = client or SabangnetProductClient()
    product_codes = order.items.exclude(sabangnet_product_code="").values_list(
        "sabangnet_product_code", flat=True
    ).distinct()
    synced = []
    for product_code in product_codes:
        product_data = client.fetch_product(product_code=product_code)
        synced.append(sync_product_safely(product_data))
    if not synced:
        raise SabangnetProductError("주문에 동기화할 사방넷 상품코드가 없습니다.")
    return synced


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


def _sync_product_category(payload):
    code = str(
        _value(
            payload,
            "categoryCode",
            "myCategoryCode",
            "myCategoryCodeS",
            "myCategoryCodeM",
            "myCategoryCodeL",
            "CATEGORY_CODE",
            default="",
        )
    ).strip()
    name = str(_value(payload, "categoryName", "myCategoryName", "CATEGORY_NAME", default="")).strip()
    if not code:
        return None
    category = Category.objects.filter(sabangnet_code=code).first()
    if category:
        return category
    return Category.objects.create(
        sabangnet_code=code, name=name or code, slug=_unique_category_slug(name or code), level=1
    )


def _unique_category_slug(name, parent=None):
    base = slugify(name, allow_unicode=True) or f"category-{hashlib.sha1(name.encode()).hexdigest()[:8]}"
    slug = base
    suffix = 1
    while Category.objects.filter(parent=parent, slug=slug).exists():
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug


def _sync_variants(product, payload):
    option_info = _value(payload, "optionInfo", default={}) or {}
    options = _value(option_info, "options", default=[]) or []
    synced = []
    if not options:
        existing = list(product.variants.order_by("pk"))
        if existing:
            return existing
        product_supply_status = str(
            _value(payload, "productSupplyStatusCode", "SUPPLY_STATUS", default="")
        )
        default_supply_status = "SALE" if product_supply_status in {"IN_SUPPLY", "SALE"} else (
            product_supply_status or "SOLD_OUT"
        )
        return [
            ProductVariant.objects.create(
                product=product,
                variant_code=f"SABANGNET-DEFAULT-{product.pk}",
                option_display_name="기본 옵션",
                stock_quantity=_integer(_value(payload, "stockQuantity", "stockQty")),
                supply_status=default_supply_status,
                synced_at=timezone.now(),
            )
        ]
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


def _sync_attributes(product, payload):
    rows = _value(payload, "attributes", "productAttributes", "attributeInfo", default=[]) or []
    values = []
    if isinstance(rows, dict):
        rows = [{"name": key, "value": value} for key, value in rows.items()]
    for row in rows:
        name = str(_value(row, "name", "attributeName", "optionName", default="")).strip()
        value = str(_value(row, "value", "attributeValue", "optionValue", default="")).strip()
        if name and value:
            values.append((name, value))
    option_rows = _value(_value(payload, "optionInfo", default={}) or {}, "options", default=[]) or []
    for row in option_rows:
        name = str(_value(row, "optionName", default="")).strip()
        value = str(_value(row, "optionDetailName", default="")).strip()
        if name and value:
            values.append((name, value))
    keep = []
    for index, (name, value) in enumerate(dict.fromkeys(values)):
        attribute, _ = ProductAttribute.objects.update_or_create(
            product=product, name=name, value=value,
            defaults={"source": "sabangnet", "sort_order": index, "is_filterable": True},
        )
        keep.append(attribute.pk)
    product.attributes.filter(source="sabangnet").exclude(pk__in=keep).delete()


def _sync_information_notice(product, payload):
    notice = _value(payload, "productInfoNotice", "productInformationNotice", "noticeInfo", default=None)
    if not notice:
        return
    if isinstance(notice, list):
        fields = {}
        for row in notice:
            name = str(_value(row, "name", "itemName", "title", default="")).strip()
            value = str(_value(row, "value", "itemValue", "content", default="")).strip()
            if name:
                fields[name] = value
        notice_type = ""
    else:
        notice_type = str(_value(notice, "type", "noticeType", default=""))
        fields = _value(notice, "fields", "items", default=notice) or {}
    ProductInformationNotice.objects.update_or_create(
        product=product,
        defaults={"notice_type": notice_type, "fields": fields, "source": "sabangnet", "synced_at": timezone.now()},
    )


def _sync_listings(product, variants):
    sync_sabangnet_listings(product, variants)


def _extract_product(payload):
    if isinstance(payload, list):
        return payload[0] if payload else None
    if not isinstance(payload, dict):
        return None
    if _value(payload, "productCode", "PRODUCT_CODE"):
        return payload
    for key in ("product", "response", "data", "data_list", "result", "items", "products"):
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
    excluded = {"token", "accesstoken", "secret", "password", "svcacntid"}
    return {key: value for key, value in payload.items() if key.lower() not in excluded}


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
