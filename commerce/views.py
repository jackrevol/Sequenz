from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Cart, CartItem, Order, OrderItem, PaymentAttempt, hash_guest_key
from .serializers import CartItemCreateSerializer, CartItemSerializer, OrderCreateSerializer, OrderSerializer


def get_guest_hash(request):
    raw_key = request.headers.get("X-Guest-Key")
    if not raw_key:
        return None
    return hash_guest_key(raw_key)


def get_active_cart(request):
    guest_hash = get_guest_hash(request)
    if not guest_hash:
        return None
    cart, _ = Cart.objects.get_or_create(guest_key_hash=guest_hash, status=Cart.Status.ACTIVE)
    return cart


class CartItemView(APIView):
    def get(self, request):
        cart = get_active_cart(request)
        if cart is None:
            return Response({"detail": "X-Guest-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = CartItemSerializer(cart.items.select_related("listing", "listing_variant__variant"), many=True)
        return Response({"results": serializer.data})

    def post(self, request):
        cart = get_active_cart(request)
        if cart is None:
            return Response({"detail": "X-Guest-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = CartItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing_variant = serializer.context["listing_variant"]
        quantity = serializer.validated_data["quantity"]
        item, created = CartItem.objects.update_or_create(
            cart=cart,
            listing_variant=listing_variant,
            defaults={
                "listing": listing_variant.listing,
                "quantity": quantity,
                "unit_price_snapshot": listing_variant.listing.selling_price_snapshot
                + listing_variant.additional_amount_snapshot,
            },
        )
        return Response(CartItemSerializer(item).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class OrderView(APIView):
    @transaction.atomic
    def post(self, request):
        cart = get_active_cart(request)
        if cart is None:
            return Response({"detail": "X-Guest-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        cart_items = list(cart.items.select_related("listing", "listing_variant__variant", "listing__product"))
        if not cart_items:
            return Response({"detail": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        subtotal = sum(item.line_total for item in cart_items)
        order = Order.objects.create(
            order_number=Order.new_order_number(),
            guest_order_key_hash=cart.guest_key_hash,
            buyer_name=data["buyer_name"],
            buyer_phone=data["buyer_phone"],
            buyer_email=data.get("buyer_email", ""),
            recipient_name=data["recipient_name"],
            recipient_phone=data["recipient_phone"],
            postal_code=data["postal_code"],
            address1=data["address1"],
            address2=data.get("address2", ""),
            delivery_memo=data.get("delivery_memo", ""),
            items_subtotal=subtotal,
            shipping_fee=0,
            payment_amount=subtotal,
        )
        for item in cart_items:
            listing = item.listing
            variant = item.listing_variant.variant
            product = listing.product
            OrderItem.objects.create(
                order=order,
                listing=listing,
                listing_variant=item.listing_variant,
                listing_code_snapshot=listing.listing_code,
                listing_name_snapshot=listing.display_name,
                listing_price_source_snapshot=listing.price_source,
                product_name_snapshot=product.name,
                option_name_snapshot=variant.option_display_name,
                sabangnet_product_code=product.sabangnet_product_code,
                custom_product_code=product.custom_product_code or "",
                barcode_snapshot=variant.barcode,
                ordered_quantity=item.quantity,
                unit_price=item.unit_price_snapshot,
                line_total=item.line_total,
            )
        PaymentAttempt.objects.create(
            order=order,
            customer_key_hash=cart.guest_key_hash or "",
            toss_order_id=order.order_number,
            order_name=_order_name(cart_items),
            expected_amount=order.payment_amount,
        )
        cart.status = Cart.Status.ORDERED
        cart.save(update_fields=["status", "updated_at"])
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


def _order_name(cart_items):
    first = cart_items[0].listing.display_name
    extra_count = len(cart_items) - 1
    if extra_count <= 0:
        return first
    return f"{first} 외 {extra_count}건"
