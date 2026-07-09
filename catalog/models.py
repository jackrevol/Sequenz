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


class ProductListing(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        ENDED = "ended", "Ended"
        ARCHIVED = "archived", "Archived"

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
        ACTIVE = "active", "Active"
        HIDDEN = "hidden", "Hidden"
        SOLD_OUT = "sold_out", "Sold out"
        PAUSED = "paused", "Paused"

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
