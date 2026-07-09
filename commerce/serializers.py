from rest_framework import serializers

from catalog.models import ProductListingVariant

from .models import CartItem, Order


class CartItemCreateSerializer(serializers.Serializer):
    listing_variant_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)

    def validate_listing_variant_id(self, value):
        try:
            listing_variant = ProductListingVariant.objects.select_related(
                "listing",
                "variant",
                "listing__product",
            ).get(id=value)
        except ProductListingVariant.DoesNotExist as exc:
            raise serializers.ValidationError("Unknown listing variant.") from exc
        if listing_variant.status != ProductListingVariant.Status.ACTIVE:
            raise serializers.ValidationError("Listing variant is not active.")
        if listing_variant.listing.status != "active":
            raise serializers.ValidationError("Listing is not active.")
        if listing_variant.variant.stock_quantity <= 0:
            raise serializers.ValidationError("Variant is out of stock.")
        self.context["listing_variant"] = listing_variant
        return value


class CartItemSerializer(serializers.ModelSerializer):
    listing_variant_id = serializers.IntegerField(source="listing_variant.id")
    listing_id = serializers.IntegerField(source="listing.id")
    display_name = serializers.CharField(source="listing.display_name")
    option_display_name = serializers.CharField(source="listing_variant.variant.option_display_name")

    class Meta:
        model = CartItem
        fields = [
            "id",
            "listing_id",
            "listing_variant_id",
            "display_name",
            "option_display_name",
            "quantity",
            "unit_price_snapshot",
            "line_total",
        ]


class OrderCreateSerializer(serializers.Serializer):
    buyer_name = serializers.CharField(max_length=120)
    buyer_phone = serializers.CharField(max_length=40)
    buyer_email = serializers.EmailField(required=False, allow_blank=True)
    recipient_name = serializers.CharField(max_length=120)
    recipient_phone = serializers.CharField(max_length=40)
    postal_code = serializers.CharField(max_length=20)
    address1 = serializers.CharField(max_length=240)
    address2 = serializers.CharField(max_length=240, required=False, allow_blank=True)
    delivery_memo = serializers.CharField(max_length=240, required=False, allow_blank=True)


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "items_subtotal",
            "shipping_fee",
            "payment_amount",
        ]


class TossPaymentConfirmSerializer(serializers.Serializer):
    order_number = serializers.CharField(max_length=40)
    payment_key = serializers.CharField(max_length=200)
    amount = serializers.IntegerField(min_value=0)
    method = serializers.CharField(max_length=40, required=False, allow_blank=True)
