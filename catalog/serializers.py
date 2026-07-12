from rest_framework import serializers

from .models import Brand, Category, Product, ProductAttribute, ProductImage, ProductInformationNotice, ProductListing, ProductListingVariant, SearchKeyword


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image_url", "alt_text", "sort_order", "is_primary"]


class ProductAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttribute
        fields = ["name", "value"]


class ProductInformationNoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductInformationNotice
        fields = ["notice_type", "fields", "updated_at"]


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "slug", "logo_image", "hero_image", "description"]


class CategorySerializer(serializers.ModelSerializer):
    parent_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "parent_id", "name", "slug", "level"]


class ProductSummarySerializer(serializers.ModelSerializer):
    brand = BrandSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    attributes = ProductAttributeSerializer(many=True, read_only=True)
    information_notice = ProductInformationNoticeSerializer(read_only=True)

    class Meta:
        model = Product
        fields = ["id", "sabangnet_product_code", "custom_product_code", "name", "detail_html", "brand", "category", "images", "attributes", "information_notice"]


class SearchKeywordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchKeyword
        fields = ["keyword", "search_count", "is_recommended"]


class ProductListingVariantSerializer(serializers.ModelSerializer):
    option_display_name = serializers.CharField(source="variant.option_display_name")
    stock_quantity = serializers.IntegerField(source="variant.available_quantity")
    supply_status = serializers.CharField(source="variant.supply_status")

    class Meta:
        model = ProductListingVariant
        fields = [
            "id",
            "status",
            "option_display_name",
            "additional_amount_snapshot",
            "stock_quantity",
            "supply_status",
        ]


class ProductListingSerializer(serializers.ModelSerializer):
    product = ProductSummarySerializer(read_only=True)
    variants = ProductListingVariantSerializer(many=True, read_only=True)

    class Meta:
        model = ProductListing
        fields = [
            "id",
            "listing_code",
            "display_name",
            "slug",
            "status",
            "consumer_price_snapshot",
            "selling_price_snapshot",
            "is_featured",
            "is_new_label",
            "is_sale_label",
            "listing_summary",
            "listing_detail_html",
            "discount_rate_snapshot",
            "product",
            "variants",
        ]
