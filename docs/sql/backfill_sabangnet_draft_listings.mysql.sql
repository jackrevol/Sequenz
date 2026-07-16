-- MySQL 8.x / catalog migration 0006 이후 실행
-- 운영 작업자와 사방넷 동기화 worker를 잠시 중지한 상태에서 1회 실행한다.
-- 모든 INSERT는 기존 레코드가 있으면 건너뛰므로 재실행해도 중복 생성하지 않는다.

START TRANSACTION;
SET @backfill_started_at = UTC_TIMESTAMP(6);

-- 옵션이 하나도 없는 기존 사방넷 상품에는 검토용 기본 옵션을 만든다.
-- 재고를 임의로 판매 가능하게 만들지 않도록 0으로 생성한다.
INSERT INTO catalog_productvariant (
    product_id,
    variant_code,
    sabangnet_option_id,
    barcode,
    option_display_name,
    additional_amount,
    stock_quantity,
    reserved_quantity,
    safety_stock_quantity,
    supply_status,
    synced_at,
    created_at,
    updated_at
)
SELECT
    p.id,
    CONCAT('SABANGNET-DEFAULT-', p.id),
    '',
    '',
    '기본 옵션',
    0,
    0,
    0,
    0,
    CASE
        WHEN p.supply_status IN ('IN_SUPPLY', 'SALE') THEN 'SALE'
        ELSE COALESCE(NULLIF(p.supply_status, ''), 'SOLD_OUT')
    END,
    p.synced_at,
    @backfill_started_at,
    @backfill_started_at
FROM catalog_product AS p
WHERE TRIM(p.sabangnet_product_code) <> ''
  AND NOT EXISTS (
      SELECT 1
      FROM catalog_productvariant AS existing_variant
      WHERE existing_variant.product_id = p.id
  );

-- 메인몰 판매 상품이 없는 기존 사방넷 상품을 작성 중으로 만든다.
INSERT INTO catalog_productlisting (
    product_id,
    listing_code,
    sales_channel,
    status,
    display_name,
    slug,
    listing_summary,
    listing_detail_html,
    seo_title,
    seo_description,
    starts_at,
    ends_at,
    sort_order,
    is_featured,
    is_new_label,
    is_sale_label,
    consumer_price_snapshot,
    selling_price_snapshot,
    discount_rate_snapshot,
    price_source,
    search_keywords,
    created_at,
    updated_at
)
SELECT
    p.id,
    CONCAT('SABANGNET-', p.id),
    'main_mall',
    'draft',
    p.name,
    CONCAT('product-', p.id),
    '',
    p.detail_html,
    p.name,
    '',
    NULL,
    NULL,
    0,
    0,
    0,
    0,
    p.consumer_price,
    p.selling_price,
    NULL,
    'sabangnet',
    p.product_tags,
    @backfill_started_at,
    @backfill_started_at
FROM catalog_product AS p
WHERE TRIM(p.sabangnet_product_code) <> ''
  AND NOT EXISTS (
      SELECT 1
      FROM catalog_productlisting AS existing_listing
      WHERE existing_listing.product_id = p.id
        AND existing_listing.sales_channel = 'main_mall'
  );

-- 작성 중 사방넷 판매 상품에 모든 상품 옵션을 작성 중으로 연결한다.
INSERT INTO catalog_productlistingvariant (
    listing_id,
    variant_id,
    status,
    additional_amount_snapshot,
    stock_display_policy,
    sort_order,
    created_at,
    updated_at
)
SELECT
    listing.id,
    variant.id,
    'draft',
    variant.additional_amount,
    'show',
    0,
    @backfill_started_at,
    @backfill_started_at
FROM catalog_productlisting AS listing
INNER JOIN catalog_product AS product
    ON product.id = listing.product_id
INNER JOIN catalog_productvariant AS variant
    ON variant.product_id = product.id
WHERE listing.sales_channel = 'main_mall'
  AND listing.price_source = 'sabangnet'
  AND listing.status = 'draft'
  AND TRIM(product.sabangnet_product_code) <> ''
  AND NOT EXISTS (
      SELECT 1
      FROM catalog_productlistingvariant AS existing_listing_variant
      WHERE existing_listing_variant.listing_id = listing.id
        AND existing_listing_variant.variant_id = variant.id
  );

COMMIT;

SELECT
    COUNT(DISTINCT listing.id) AS draft_listing_count,
    COUNT(listing_variant.id) AS draft_listing_variant_count
FROM catalog_productlisting AS listing
LEFT JOIN catalog_productlistingvariant AS listing_variant
    ON listing_variant.listing_id = listing.id
   AND listing_variant.status = 'draft'
WHERE listing.sales_channel = 'main_mall'
  AND listing.price_source = 'sabangnet'
  AND listing.status = 'draft';
