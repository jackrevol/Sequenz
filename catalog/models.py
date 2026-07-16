from django.db import models
from django.db.models import Q


class Brand(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    logo_image = models.URLField(blank=True)
    hero_image = models.URLField(blank=True)
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Category(models.Model):
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    level = models.PositiveSmallIntegerField(default=1)
    sort_order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    sabangnet_code = models.CharField(max_length=80, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["level", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["slug"],
                condition=Q(parent__isnull=True),
                name="unique_root_category_slug",
            ),
            models.UniqueConstraint(
                fields=["parent", "slug"],
                condition=Q(parent__isnull=False),
                name="unique_child_category_slug",
            ),
        ]

    def __str__(self):
        return self.name


class Product(models.Model):
    brand = models.ForeignKey(
        Brand,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="products",
    )
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="products",
    )
    sabangnet_product_code = models.CharField(max_length=80, unique=True)
    custom_product_code = models.CharField(max_length=80, blank=True, null=True, unique=True)
    name = models.CharField(max_length=240)
    english_name = models.CharField(max_length=240, blank=True)
    model_name = models.CharField(max_length=120, blank=True)
    manufacturer_name = models.CharField(max_length=120, blank=True)
    origin_name = models.CharField(max_length=120, blank=True)
    consumer_price = models.PositiveBigIntegerField(default=0)
    selling_price = models.PositiveBigIntegerField(default=0)
    cost_price = models.PositiveBigIntegerField(null=True, blank=True)
    tax_code = models.CharField(max_length=40)
    supply_status = models.CharField(max_length=40, db_index=True)
    target_code = models.CharField(max_length=40, blank=True)
    season_code = models.CharField(max_length=40, blank=True)
    product_tags = models.CharField(max_length=500, blank=True)
    detail_html = models.TextField(blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)
    raw_sabangnet_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["brand", "category", "supply_status"]),
            models.Index(fields=["selling_price"]),
        ]

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="variants")
    variant_code = models.CharField(max_length=120, blank=True, null=True, unique=True)
    sabangnet_option_id = models.CharField(max_length=120, blank=True, db_index=True)
    barcode = models.CharField(max_length=120, blank=True, db_index=True)
    option_display_name = models.CharField(max_length=240)
    additional_amount = models.BigIntegerField(default=0)
    stock_quantity = models.IntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    safety_stock_quantity = models.IntegerField(default=0)
    supply_status = models.CharField(max_length=40, db_index=True)
    synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "option_display_name"],
                name="unique_variant_display_name_per_product",
            ),
            models.UniqueConstraint(
                fields=["barcode"],
                condition=~Q(barcode=""),
                name="unique_nonblank_variant_barcode",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} / {self.option_display_name}"

    @property
    def available_quantity(self):
        return max(self.stock_quantity - self.reserved_quantity, 0)


class ProductImage(models.Model):
    class Source(models.TextChoices):
        SABANGNET = "sabangnet", "사방넷"
        ADMIN = "admin", "관리자 등록"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.SABANGNET)
    sabangnet_image_srno = models.CharField(max_length=80, blank=True)
    image_url = models.URLField(max_length=1000)
    alt_text = models.CharField(max_length=240, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "source", "sabangnet_image_srno"],
                condition=~Q(sabangnet_image_srno=""),
                name="unique_product_source_image_srno",
            ),
            models.UniqueConstraint(
                fields=["product"], condition=Q(is_primary=True), name="unique_primary_image_per_product"
            ),
        ]


class ProductInformationNotice(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="information_notice")
    notice_type = models.CharField(max_length=120, blank=True)
    fields = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=20, default="sabangnet")
    synced_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class ProductAttribute(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="attributes")
    name = models.CharField(max_length=80, db_index=True)
    value = models.CharField(max_length=160, db_index=True)
    is_filterable = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=20, default="sabangnet")

    class Meta:
        ordering = ["sort_order", "name", "value"]
        constraints = [
            models.UniqueConstraint(fields=["product", "name", "value"], name="unique_product_attribute_value")
        ]


class SearchKeyword(models.Model):
    keyword = models.CharField(max_length=120, unique=True)
    search_count = models.PositiveBigIntegerField(default=0)
    is_recommended = models.BooleanField(default=False, db_index=True)
    is_visible = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    last_searched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["sort_order", "-search_count", "keyword"]


class ProductSyncSnapshot(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "신규 등록"
        UPDATED = "updated", "정보 갱신"
        FAILED = "failed", "실패"

    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL, related_name="sync_snapshots")
    sabangnet_product_code = models.CharField(max_length=80, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, db_index=True)
    field_changes = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    synced_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-synced_at"]


class ProductListing(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "작성 중"
        SCHEDULED = "scheduled", "게시 예정"
        ACTIVE = "active", "판매 중"
        PAUSED = "paused", "판매 일시중지"
        ENDED = "ended", "판매 종료"
        ARCHIVED = "archived", "보관"

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="listings")
    listing_code = models.CharField(max_length=80, unique=True)
    sales_channel = models.CharField(max_length=40, default="main_mall")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    display_name = models.CharField(max_length=240)
    slug = models.SlugField(max_length=260)
    listing_summary = models.TextField(blank=True)
    listing_detail_html = models.TextField(blank=True)
    seo_title = models.CharField(max_length=240, blank=True)
    seo_description = models.CharField(max_length=500, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    is_new_label = models.BooleanField(default=False)
    is_sale_label = models.BooleanField(default=False)
    consumer_price_snapshot = models.PositiveBigIntegerField(default=0)
    selling_price_snapshot = models.PositiveBigIntegerField(default=0)
    discount_rate_snapshot = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    price_source = models.CharField(max_length=40, default="sabangnet")
    search_keywords = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "sales_channel"],
                condition=Q(status="active"),
                name="unique_active_listing_per_product_channel",
            ),
            models.UniqueConstraint(
                fields=["slug"],
                condition=Q(status__in=["active", "scheduled"]),
                name="unique_public_listing_slug",
            ),
        ]
        indexes = [
            models.Index(fields=["sales_channel", "status", "starts_at", "ends_at"]),
        ]

    def __str__(self):
        return self.display_name


class ProductListingVariant(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "작성 중"
        ACTIVE = "active", "판매 중"
        HIDDEN = "hidden", "숨김"
        SOLD_OUT = "sold_out", "품절"
        PAUSED = "paused", "판매 일시중지"

    listing = models.ForeignKey(ProductListing, on_delete=models.CASCADE, related_name="variants")
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="listing_variants")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    additional_amount_snapshot = models.BigIntegerField(default=0)
    stock_display_policy = models.CharField(max_length=40, default="show")
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "variant"],
                name="unique_variant_per_listing",
            )
        ]

    def __str__(self):
        return f"{self.listing.display_name} / {self.variant.option_display_name}"
