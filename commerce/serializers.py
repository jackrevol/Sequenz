from rest_framework import serializers

from catalog.models import ProductListingVariant

from .models import CartItem, Order, OrderClaim, OrderClaimItem, OrderItem, Shipment


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
        if listing_variant.variant.available_quantity <= 0:
            raise serializers.ValidationError("Variant is out of stock.")
        self.context["listing_variant"] = listing_variant
        return value


class CartItemUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, required=False)
    listing_variant_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("변경할 수량 또는 옵션이 필요합니다.")
        variant_id = attrs.get("listing_variant_id")
        if variant_id is not None:
            create = CartItemCreateSerializer(
                data={"listing_variant_id": variant_id, "quantity": attrs.get("quantity", 1)}
            )
            create.is_valid(raise_exception=True)
            attrs["listing_variant"] = create.context["listing_variant"]
        return attrs


class CartBulkActionSerializer(serializers.Serializer):
    item_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    action = serializers.ChoiceField(choices=["delete", "move_to_wishlist"])


class CartItemSerializer(serializers.ModelSerializer):
    listing_variant_id = serializers.IntegerField(source="listing_variant.id")
    listing_id = serializers.IntegerField(source="listing.id")
    display_name = serializers.CharField(source="listing.display_name")
    option_display_name = serializers.CharField(source="listing_variant.variant.option_display_name")
    available_variants = serializers.SerializerMethodField()

    def get_available_variants(self, item):
        return [
            {
                "id": variant.id,
                "option_display_name": variant.variant.option_display_name,
                "stock_quantity": variant.variant.available_quantity,
            }
            for variant in item.listing.variants.all()
            if variant.status == ProductListingVariant.Status.ACTIVE and variant.variant.available_quantity > 0
        ]

    class Meta:
        model = CartItem
        fields = [
            "id",
            "listing_id",
            "listing_variant_id",
            "display_name",
            "option_display_name",
            "available_variants",
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
    coupon_code = serializers.CharField(max_length=80, required=False, allow_blank=True)
    point_to_use = serializers.IntegerField(min_value=0, required=False, default=0)
    cart_item_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=False)


class OrderSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    shipments = serializers.SerializerMethodField()

    def get_items(self, order):
        return OrderItemSerializer(order.items.all(), many=True).data

    def get_shipments(self, order):
        return ShipmentSerializer(order.shipments.all(), many=True).data

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "fulfillment_status",
            "items_subtotal",
            "shipping_fee",
            "coupon_discount_amount",
            "point_used_amount",
            "payment_amount",
            "buyer_name",
            "recipient_name",
            "postal_code",
            "address1",
            "address2",
            "ordered_at",
            "items",
            "shipments",
        ]


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id", "listing_name_snapshot", "product_name_snapshot", "option_name_snapshot",
            "ordered_quantity", "cancelled_quantity", "returned_quantity", "unit_price", "line_total",
            "review_status",
        ]


class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = [
            "id", "carrier_code", "carrier_name", "tracking_number", "status",
            "shipped_at", "delivered_at", "synced_at",
        ]


class TossPaymentConfirmSerializer(serializers.Serializer):
    order_number = serializers.CharField(max_length=40)
    payment_key = serializers.CharField(max_length=200)
    amount = serializers.IntegerField(min_value=0)
    method = serializers.CharField(max_length=40, required=False, allow_blank=True)


class OrderCancellationSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=240)


class OrderClaimItemInputSerializer(serializers.Serializer):
    order_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class OrderClaimCreateSerializer(serializers.Serializer):
    claim_type = serializers.ChoiceField(choices=[
        OrderClaim.ClaimType.EXCHANGE,
        OrderClaim.ClaimType.RETURN,
    ])
    reason = serializers.CharField(max_length=240)
    detail = serializers.CharField(required=False, allow_blank=True)
    items = OrderClaimItemInputSerializer(many=True, allow_empty=False)


class OrderClaimItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="order_item.product_name_snapshot")
    option_name = serializers.CharField(source="order_item.option_name_snapshot")

    class Meta:
        model = OrderClaimItem
        fields = ["order_item_id", "product_name", "option_name", "quantity"]


class OrderClaimSerializer(serializers.ModelSerializer):
    items = OrderClaimItemSerializer(many=True, read_only=True)

    class Meta:
        model = OrderClaim
        fields = [
            "id", "claim_type", "status", "reason", "detail", "refund_amount",
            "restored_point_amount", "items", "requested_at", "completed_at",
        ]


class GuestOrderLookupSerializer(serializers.Serializer):
    order_number = serializers.CharField(max_length=40)
    buyer_name = serializers.CharField(max_length=120)
    buyer_phone = serializers.CharField(max_length=40)
