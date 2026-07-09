from rest_framework import serializers

from .models import Product, ProductListing, ProductListingVariant


class ProductSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "sabangnet_product_code", "custom_product_code", "name"]


class ProductListingVariantSerializer(serializers.ModelSerializer):
    option_display_name = serializers.CharField(source="variant.option_display_name")
    stock_quantity = serializers.IntegerField(source="variant.stock_quantity")
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
            "product",
            "variants",
        ]
