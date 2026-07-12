from django.contrib import admin

from .models import Brand, Category, Product, ProductImage, ProductListing, ProductListingVariant, ProductSyncSnapshot, ProductVariant


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_visible", "sort_order", "updated_at")
    list_editable = ("is_visible", "sort_order")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "level", "is_visible", "sort_order")
    list_filter = ("level", "is_visible")
    list_editable = ("is_visible", "sort_order")
    search_fields = ("name", "slug", "sabangnet_code")


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ("option_display_name", "variant_code", "barcode", "stock_quantity", "safety_stock_quantity", "supply_status")
    readonly_fields = ("variant_code", "barcode")


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ("source", "image_url", "alt_text", "sort_order", "is_primary", "sabangnet_image_srno")
    readonly_fields = ("sabangnet_image_srno",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "custom_product_code", "brand", "category", "selling_price", "supply_status", "synced_at")
    list_filter = ("brand", "category", "supply_status")
    search_fields = ("name", "custom_product_code", "sabangnet_product_code", "product_tags")
    readonly_fields = ("sabangnet_product_code", "raw_sabangnet_payload", "synced_at")
    inlines = (ProductVariantInline, ProductImageInline)


class ProductListingVariantInline(admin.TabularInline):
    model = ProductListingVariant
    extra = 0
    autocomplete_fields = ("variant",)


@admin.register(ProductListing)
class ProductListingAdmin(admin.ModelAdmin):
    list_display = ("display_name", "listing_code", "status", "selling_price_snapshot", "is_featured", "sort_order", "updated_at")
    list_filter = ("status", "is_featured", "is_new_label", "is_sale_label", "sales_channel")
    list_editable = ("status", "is_featured", "sort_order")
    search_fields = ("display_name", "listing_code", "slug", "search_keywords")
    prepopulated_fields = {"slug": ("display_name",)}
    autocomplete_fields = ("product",)
    inlines = (ProductListingVariantInline,)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("product", "option_display_name", "variant_code", "stock_quantity", "safety_stock_quantity", "supply_status")
    list_filter = ("supply_status",)
    search_fields = ("product__name", "variant_code", "barcode", "option_display_name")


@admin.register(ProductSyncSnapshot)
class ProductSyncSnapshotAdmin(admin.ModelAdmin):
    list_display = ("sabangnet_product_code", "product", "status", "synced_at")
    list_filter = ("status", "synced_at")
    search_fields = ("sabangnet_product_code", "product__name", "error_message")
    readonly_fields = tuple(field.name for field in ProductSyncSnapshot._meta.fields)
