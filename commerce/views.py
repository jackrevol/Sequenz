import hashlib
import hmac
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.models import SabangnetOrderExport
from integrations.toss import TossPaymentError, cancel_toss_payment, confirm_toss_payment
from benefits.services import (
    BenefitValidationError,
    apply_order_benefits,
    quote_member_benefits,
    restore_order_benefits,
    shipping_fee_for,
)
from accounts.models import WishlistItem
from catalog.models import ProductListingVariant, ProductVariant

from .models import (
    Cart, CartItem, Order, OrderCancellation, OrderClaim, OrderClaimItem, OrderItem,
    OrderStatusHistory, Payment, PaymentAttempt, hash_guest_key,
)
from .inventory import InventoryReservationError, release_order_inventory, reserve_order_inventory
from .serializers import (
    CartItemCreateSerializer,
    CartBulkActionSerializer,
    CartItemUpdateSerializer,
    CartItemSerializer,
    OrderCreateSerializer,
    OrderCancellationSerializer,
    OrderClaimCreateSerializer,
    OrderClaimSerializer,
    GuestOrderLookupSerializer,
    OrderSerializer,
    TossPaymentConfirmSerializer,
)


def get_guest_hash(request):
    raw_key = request.headers.get("X-Guest-Key")
    if not raw_key:
        return None
    return hash_guest_key(raw_key)


def get_active_cart(request):
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user, status=Cart.Status.ACTIVE)
        return cart
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
        serializer = CartItemSerializer(
            cart.items.select_related("listing", "listing_variant__variant").prefetch_related(
                "listing__variants__variant"
            ), many=True
        )
        return Response({
            "results": serializer.data,
            "summary": _cart_summary(cart),
        })

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


class CartItemDetailView(APIView):
    def _get_item(self, request, pk):
        cart = get_active_cart(request)
        if cart is None:
            return None, Response({"detail": "X-Guest-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            return cart.items.select_related("listing", "listing_variant__variant").get(pk=pk), None
        except CartItem.DoesNotExist:
            return None, Response({"detail": "Unknown cart item."}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, pk):
        item, error = self._get_item(request, pk)
        if error:
            return error
        serializer = CartItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quantity = serializer.validated_data.get("quantity", item.quantity)
        listing_variant = serializer.validated_data.get("listing_variant", item.listing_variant)
        if listing_variant.variant.available_quantity < quantity:
            return Response({"detail": "Requested quantity exceeds stock."}, status=status.HTTP_400_BAD_REQUEST)
        if listing_variant.listing_id != item.listing_id:
            return Response({"detail": "같은 상품의 옵션만 변경할 수 있습니다."}, status=status.HTTP_400_BAD_REQUEST)
        existing = item.cart.items.filter(listing_variant=listing_variant).exclude(pk=item.pk).first()
        if existing:
            combined = existing.quantity + quantity
            if listing_variant.variant.available_quantity < combined:
                return Response({"detail": "Requested quantity exceeds stock."}, status=status.HTTP_400_BAD_REQUEST)
            existing.quantity = combined
            existing.save(update_fields=["quantity", "updated_at"])
            item.delete()
            return Response(CartItemSerializer(existing).data)
        item.quantity = quantity
        item.listing_variant = listing_variant
        item.unit_price_snapshot = listing_variant.listing.selling_price_snapshot + listing_variant.additional_amount_snapshot
        item.save(update_fields=["quantity", "listing_variant", "unit_price_snapshot", "updated_at"])
        return Response(CartItemSerializer(item).data)

    def delete(self, request, pk):
        item, error = self._get_item(request, pk)
        if error:
            return error
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartItemBulkView(APIView):
    @transaction.atomic
    def post(self, request):
        cart = get_active_cart(request)
        if cart is None:
            return Response({"detail": "X-Guest-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = CartBulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        items = cart.items.filter(pk__in=serializer.validated_data["item_ids"])
        if items.count() != len(set(serializer.validated_data["item_ids"])):
            return Response({"detail": "장바구니 상품을 확인해 주세요."}, status=status.HTTP_400_BAD_REQUEST)
        if serializer.validated_data["action"] == "move_to_wishlist":
            if not request.user.is_authenticated:
                return Response({"detail": "로그인 후 찜으로 이동할 수 있습니다."}, status=status.HTTP_403_FORBIDDEN)
            WishlistItem.objects.bulk_create(
                [WishlistItem(user=request.user, listing=item.listing) for item in items], ignore_conflicts=True
            )
        deleted = items.count()
        items.delete()
        return Response({"processed_count": deleted, "summary": _cart_summary(cart)})


class CartBenefitQuoteView(APIView):
    def post(self, request):
        cart = get_active_cart(request)
        if cart is None:
            return Response({"detail": "X-Guest-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        items = _selected_cart_items(cart, request.data.get("cart_item_ids"))
        if items is None:
            return Response({"detail": "장바구니 상품을 확인해 주세요."}, status=status.HTTP_400_BAD_REQUEST)
        subtotal = sum(item.line_total for item in items)
        if subtotal <= 0:
            return Response({"detail": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            quote = quote_member_benefits(
                request.user, subtotal, request.data.get("coupon_code", ""), request.data.get("point_to_use", 0)
            )
        except (BenefitValidationError, TypeError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({key: quote[key] for key in (
            "shipping_fee", "coupon_discount_amount", "point_used_amount", "payment_amount"
        )})


def _cart_summary(cart):
    items = list(cart.items.all())
    subtotal = sum(item.line_total for item in items)
    shipping_fee = shipping_fee_for(subtotal)
    return {
        "item_count": sum(item.quantity for item in items),
        "items_subtotal": subtotal,
        "shipping_fee": shipping_fee,
        "payment_amount": subtotal + shipping_fee,
    }


class OrderView(APIView):
    @transaction.atomic
    def post(self, request):
        cart = get_active_cart(request)
        if cart is None:
            return Response({"detail": "X-Guest-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        cart = Cart.objects.select_for_update().get(pk=cart.pk)
        if cart.status != Cart.Status.ACTIVE:
            return Response({"detail": "Cart is no longer active."}, status=status.HTTP_409_CONFLICT)
        requested_ids = request.data.get("cart_item_ids")
        cart_items = _selected_cart_items(
            cart, requested_ids,
            queryset=cart.items.select_related("listing", "listing_variant__variant", "listing__product"),
        )
        if cart_items is None:
            return Response({"detail": "장바구니 상품을 확인해 주세요."}, status=status.HTTP_400_BAD_REQUEST)
        if not cart_items:
            return Response({"detail": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        now = timezone.now()
        variant_ids = [item.listing_variant.variant_id for item in cart_items]
        locked_variants = {
            variant.pk: variant for variant in ProductVariant.objects.select_for_update().filter(pk__in=variant_ids)
        }
        quantities = {}
        for item in cart_items:
            listing = item.listing
            listing_variant = item.listing_variant
            variant = locked_variants[listing_variant.variant_id]
            current_price = listing.selling_price_snapshot + listing_variant.additional_amount_snapshot
            if listing.status != "active" or (listing.starts_at and listing.starts_at > now) or (
                listing.ends_at and listing.ends_at < now
            ):
                return Response({"detail": f"{listing.display_name}은 현재 판매 중이 아닙니다."}, status=status.HTTP_409_CONFLICT)
            if listing_variant.status != "active" or variant.available_quantity < item.quantity:
                return Response({"detail": f"{listing.display_name} 옵션의 재고 또는 판매상태를 확인해 주세요."}, status=status.HTTP_409_CONFLICT)
            if item.unit_price_snapshot != current_price:
                return Response(
                    {"detail": f"{listing.display_name} 가격이 변경되었습니다.", "current_unit_price": current_price},
                    status=status.HTTP_409_CONFLICT,
                )
            quantities[variant.pk] = quantities.get(variant.pk, 0) + item.quantity
        subtotal = sum(item.line_total for item in cart_items)
        try:
            benefit_quote = quote_member_benefits(
                request.user,
                subtotal,
                coupon_code=data.get("coupon_code", ""),
                point_to_use=data.get("point_to_use", 0),
            )
        except BenefitValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        order = Order.objects.create(
            order_number=Order.new_order_number(),
            user=cart.user,
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
            shipping_fee=benefit_quote["shipping_fee"],
            coupon_discount_amount=benefit_quote["coupon_discount_amount"],
            point_used_amount=benefit_quote["point_used_amount"],
            payment_amount=benefit_quote["payment_amount"],
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
        try:
            reserve_order_inventory(order, quantities)
        except InventoryReservationError as exc:
            transaction.set_rollback(True)
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        PaymentAttempt.objects.create(
            order=order,
            customer_key_hash=cart.guest_key_hash or "",
            toss_order_id=order.order_number,
            order_name=_order_name(cart_items),
            expected_amount=order.payment_amount,
        )
        try:
            apply_order_benefits(order, benefit_quote)
        except BenefitValidationError as exc:
            transaction.set_rollback(True)
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        if requested_ids and cart.items.exclude(pk__in=[item.pk for item in cart_items]).exists():
            cart.items.filter(pk__in=[item.pk for item in cart_items]).delete()
        else:
            cart.status = Cart.Status.ORDERED
            cart.save(update_fields=["status", "updated_at"])
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetailView(APIView):
    def get(self, request, order_number):
        filters = {"order_number": order_number}
        if request.user.is_authenticated:
            filters["user"] = request.user
        else:
            guest_hash = get_guest_hash(request)
            if guest_hash is None:
                return Response({"detail": "X-Guest-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
            filters["guest_order_key_hash"] = guest_hash
        try:
            order = Order.objects.prefetch_related("items", "shipments").get(**filters)
        except Order.DoesNotExist:
            return Response({"detail": "Unknown order."}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrderSerializer(order).data)


class MemberOrderListView(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"detail": "Authentication credentials were not provided."}, status=status.HTTP_403_FORBIDDEN)
        orders = Order.objects.filter(user=request.user).prefetch_related("items", "shipments").order_by("-ordered_at")
        return Response({"results": OrderSerializer(orders, many=True).data})


class GuestOrderLookupView(APIView):
    authentication_classes = []

    def post(self, request):
        serializer = GuestOrderLookupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        order = Order.objects.prefetch_related("items", "shipments").filter(
            order_number=data["order_number"], user__isnull=True, buyer_name=data["buyer_name"]
        ).first()
        if order is None or _digits(order.buyer_phone) != _digits(data["buyer_phone"]):
            return Response({"detail": "일치하는 비회원 주문을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrderSerializer(order).data)


def _digits(value):
    return "".join(char for char in value if char.isdigit())


def _order_name(cart_items):
    first = cart_items[0].listing.display_name
    extra_count = len(cart_items) - 1
    if extra_count <= 0:
        return first
    return f"{first} 외 {extra_count}건"


def _selected_cart_items(cart, requested_ids, queryset=None):
    queryset = queryset if queryset is not None else cart.items.all()
    if not requested_ids:
        return list(queryset)
    try:
        unique_ids = {int(item_id) for item_id in requested_ids}
    except (TypeError, ValueError):
        return None
    items = list(queryset.filter(pk__in=unique_ids))
    return items if len(items) == len(unique_ids) else None


class TossPaymentConfirmView(APIView):
    @transaction.atomic
    def post(self, request):
        serializer = TossPaymentConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            order = _owned_order(request, data["order_number"], for_update=True)
            if order is None:
                raise Order.DoesNotExist
        except Order.DoesNotExist:
            return Response({"detail": "Unknown order."}, status=status.HTTP_404_NOT_FOUND)

        existing_payment = Payment.objects.filter(payment_key=data["payment_key"]).first()
        if existing_payment:
            if existing_payment.order_id != order.id:
                return Response({"detail": "Payment key belongs to another order."}, status=status.HTTP_409_CONFLICT)
            self._ensure_sabangnet_export(order)
            return Response(self._payment_response(existing_payment), status=status.HTTP_200_OK)

        if order.inventory_reservation_status != Order.InventoryReservationStatus.RESERVED:
            return Response({"detail": "주문 재고 예약이 만료되었습니다."}, status=status.HTTP_409_CONFLICT)

        if data["amount"] != order.payment_amount:
            return Response({"detail": "Payment amount does not match order amount."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            toss_response = confirm_toss_payment(data["payment_key"], order.order_number, order.payment_amount)
        except TossPaymentError as exc:
            return Response({"detail": str(exc), "code": exc.code}, status=status.HTTP_502_BAD_GATEWAY)
        if (
            toss_response.get("status") != "DONE"
            or toss_response.get("orderId") != order.order_number
            or toss_response.get("paymentKey") != data["payment_key"]
            or toss_response.get("totalAmount") != order.payment_amount
        ):
            return Response(
                {"detail": "토스 결제 승인 응답이 내부 주문과 일치하지 않습니다.", "code": "TOSS_RESPONSE_MISMATCH"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        attempt = order.payment_attempts.order_by("-created_at").first()
        if attempt is None:
            attempt = PaymentAttempt.objects.create(
                order=order,
                customer_key_hash=order.guest_order_key_hash or "",
                toss_order_id=order.order_number,
                order_name=order.items.first().listing_name_snapshot if order.items.exists() else order.order_number,
                expected_amount=order.payment_amount,
            )
        attempt.redirect_payment_key = data["payment_key"]
        attempt.redirect_amount = data["amount"]
        attempt.status = PaymentAttempt.Status.CONFIRMED
        attempt.save(update_fields=["redirect_payment_key", "redirect_amount", "status", "updated_at"])

        payment = Payment.objects.create(
            order=order,
            attempt=attempt,
            payment_key=data["payment_key"],
            toss_order_id=order.order_number,
            status=toss_response.get("status", "DONE"),
            method=toss_response.get("method", data.get("method", "")),
            total_amount=toss_response.get("totalAmount", order.payment_amount),
            balance_amount=toss_response.get("balanceAmount", order.payment_amount),
            raw_response_summary=_safe_toss_summary(toss_response),
        )
        order.status = Order.Status.PAID
        order.sabangnet_status = "pending"
        order.paid_at = timezone.now()
        order.save(update_fields=["status", "sabangnet_status", "paid_at", "updated_at"])
        self._ensure_sabangnet_export(order)
        return Response(self._payment_response(payment), status=status.HTTP_201_CREATED)

    def _ensure_sabangnet_export(self, order):
        return SabangnetOrderExport.objects.get_or_create(
            order=order,
            defaults={
                "status": SabangnetOrderExport.Status.PENDING,
                "payload_summary": {
                    "order_number": order.order_number,
                    "payment_amount": order.payment_amount,
                    "item_count": order.items.count(),
                },
            },
        )

    def _payment_response(self, payment):
        return {
            "id": payment.id,
            "order_number": payment.order.order_number,
            "payment_key": payment.payment_key,
            "status": payment.status,
            "total_amount": payment.total_amount,
            "balance_amount": payment.balance_amount,
        }


class TossPaymentPrepareView(APIView):
    def get(self, request, order_number):
        order = _owned_order(request, order_number)
        if order is None:
            return Response({"detail": "Unknown order."}, status=status.HTTP_404_NOT_FOUND)
        if order.status != Order.Status.PAYMENT_PENDING:
            return Response({"detail": "Order is not awaiting payment."}, status=status.HTTP_409_CONFLICT)
        if order.inventory_reservation_status != Order.InventoryReservationStatus.RESERVED:
            return Response({"detail": "주문 재고 예약이 만료되었습니다."}, status=status.HTTP_409_CONFLICT)
        if not settings.TOSS_CLIENT_KEY:
            return Response({"detail": "토스페이먼츠 클라이언트 키가 설정되지 않았습니다."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        attempt = order.payment_attempts.order_by("-created_at").first()
        return Response({
            "client_key": settings.TOSS_CLIENT_KEY,
            "customer_key": _toss_customer_key(order),
            "order_id": order.order_number,
            "order_name": attempt.order_name if attempt else order.order_number,
            "amount": order.payment_amount,
            "customer_name": order.buyer_name,
            "customer_email": order.buyer_email,
            "customer_mobile_phone": "".join(char for char in order.buyer_phone if char.isdigit()),
            "success_url": request.build_absolute_uri("/checkout/?payment=success"),
            "fail_url": request.build_absolute_uri("/checkout/?payment=fail"),
        })


class OrderCancellationView(APIView):
    def post(self, request, order_number):
        serializer = OrderCancellationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = _owned_order(request, order_number)
        if order is None:
            return Response({"detail": "Unknown order."}, status=status.HTTP_404_NOT_FOUND)
        if order.status == Order.Status.CANCELLED:
            cancellation = getattr(order, "cancellation", None)
            return Response(_cancellation_response(cancellation), status=status.HTTP_200_OK)
        if order.status != Order.Status.PAID:
            return Response({"detail": "Only paid orders can be cancelled."}, status=status.HTTP_409_CONFLICT)
        blocked = {
            Order.FulfillmentStatus.SHIPPED,
            Order.FulfillmentStatus.IN_TRANSIT,
            Order.FulfillmentStatus.DELIVERED,
            Order.FulfillmentStatus.RETURNED,
        }
        if order.fulfillment_status in blocked:
            return Response({"detail": "배송이 시작된 주문은 즉시 취소할 수 없습니다."}, status=status.HTTP_409_CONFLICT)
        payment = order.payments.filter(status="DONE").order_by("-created_at").first()
        if payment is None:
            return Response({"detail": "취소 가능한 결제를 찾을 수 없습니다."}, status=status.HTTP_409_CONFLICT)
        with transaction.atomic():
            cancellation, _ = OrderCancellation.objects.select_for_update().get_or_create(
                order=order,
                defaults={
                    "payment": payment,
                    "requested_by": request.user if request.user.is_authenticated else None,
                    "reason": serializer.validated_data["reason"],
                    "idempotency_key": str(uuid.uuid4()),
                    "cancel_amount": payment.balance_amount,
                },
            )
        if cancellation.status == OrderCancellation.Status.COMPLETED:
            return Response(_cancellation_response(cancellation))
        try:
            toss_response = cancel_toss_payment(payment.payment_key, cancellation.reason, cancellation.idempotency_key)
        except TossPaymentError as exc:
            cancellation.status = OrderCancellation.Status.FAILED
            cancellation.failure_code = exc.code
            cancellation.failure_message = str(exc)[:240]
            cancellation.save(update_fields=["status", "failure_code", "failure_message", "updated_at"])
            return Response({"detail": str(exc), "code": exc.code}, status=status.HTTP_502_BAD_GATEWAY)
        _complete_cancellation(cancellation.pk, toss_response)
        cancellation.refresh_from_db()
        return Response(_cancellation_response(cancellation), status=status.HTTP_200_OK)


class OrderClaimView(APIView):
    def get(self, request, order_number):
        order = _owned_order(request, order_number)
        if order is None:
            return Response({"detail": "Unknown order."}, status=status.HTTP_404_NOT_FOUND)
        claims = order.claims.prefetch_related("items__order_item")
        return Response({"results": OrderClaimSerializer(claims, many=True).data})

    def post(self, request, order_number):
        serializer = OrderClaimCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = _owned_order(request, order_number)
        if order is None:
            return Response({"detail": "Unknown order."}, status=status.HTTP_404_NOT_FOUND)
        data = serializer.validated_data
        claim_type = data["claim_type"]
        error = _validate_claim_state(order, claim_type)
        if error:
            return Response({"detail": error}, status=status.HTTP_409_CONFLICT)
        try:
            selected = _validate_claim_items(order, data["items"], claim_type)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            claim = OrderClaim.objects.create(
                order=order,
                claim_type=claim_type,
                requested_by=request.user if request.user.is_authenticated else None,
                reason=data["reason"],
                detail=data.get("detail", ""),
                refund_amount=0,
                restored_point_amount=0,
            )
            OrderClaimItem.objects.bulk_create([
                OrderClaimItem(claim=claim, order_item=item, quantity=quantity)
                for item, quantity in selected
            ])
        claim.refresh_from_db()
        return Response(OrderClaimSerializer(claim).data, status=status.HTTP_201_CREATED)


def _owned_order(request, order_number, for_update=False):
    filters = {"order_number": order_number}
    if request.user.is_authenticated:
        filters["user"] = request.user
    else:
        guest_hash = get_guest_hash(request)
        if guest_hash is None:
            return None
        filters["guest_order_key_hash"] = guest_hash
    queryset = Order.objects.select_for_update() if for_update else Order.objects
    return queryset.filter(**filters).first()


def _validate_claim_state(order, claim_type):
    if order.status != Order.Status.PAID:
        return "결제가 완료된 주문만 신청할 수 있습니다."
    if order.fulfillment_status not in {
        Order.FulfillmentStatus.SHIPPED, Order.FulfillmentStatus.IN_TRANSIT,
        Order.FulfillmentStatus.DELIVERED,
    }:
        return "배송이 시작된 주문만 교환·반품을 신청할 수 있습니다."
    return ""


def _validate_claim_items(order, requested_items, claim_type):
    ids = [entry["order_item_id"] for entry in requested_items]
    if len(ids) != len(set(ids)):
        raise ValueError("같은 주문상품을 중복 선택할 수 없습니다.")
    items = {item.id: item for item in order.items.filter(id__in=ids)}
    if len(items) != len(ids):
        raise ValueError("주문에 포함되지 않은 상품이 있습니다.")
    selected = []
    for entry in requested_items:
        item = items[entry["order_item_id"]]
        already_claimed = sum(
            claim_item.quantity for claim_item in item.claim_items.filter(
                claim__claim_type=claim_type,
                claim__status__in=[OrderClaim.Status.REQUESTED, OrderClaim.Status.PROCESSING, OrderClaim.Status.COMPLETED],
            )
        )
        if entry["quantity"] > item.ordered_quantity - already_claimed:
            raise ValueError("신청 가능 수량을 초과했습니다.")
        selected.append((item, entry["quantity"]))
    return selected


def _toss_customer_key(order):
    if order.user_id is None:
        return "ANONYMOUS"
    digest = hmac.new(settings.SECRET_KEY.encode(), f"toss:{order.user_id}".encode(), hashlib.sha256).hexdigest()
    return f"member_{digest[:32]}"


def _safe_toss_summary(payload):
    allowed = {"paymentKey", "orderId", "status", "method", "totalAmount", "balanceAmount", "approvedAt", "easyPay"}
    return {key: value for key, value in payload.items() if key in allowed}


@transaction.atomic
def _complete_cancellation(cancellation_id, toss_response):
    cancellation = OrderCancellation.objects.select_for_update().select_related("order", "payment").get(pk=cancellation_id)
    order = cancellation.order
    payment = cancellation.payment
    cancels = toss_response.get("cancels") or []
    latest = cancels[-1] if cancels else {}
    cancellation.status = OrderCancellation.Status.COMPLETED
    cancellation.transaction_key = latest.get("transactionKey", "")
    cancellation.completed_at = timezone.now()
    cancellation.failure_code = ""
    cancellation.failure_message = ""
    cancellation.save(update_fields=["status", "transaction_key", "completed_at", "failure_code", "failure_message", "updated_at"])
    payment.status = toss_response.get("status", "CANCELED")
    payment.balance_amount = toss_response.get("balanceAmount", 0)
    payment.raw_response_summary = _safe_toss_summary(toss_response)
    payment.save(update_fields=["status", "balance_amount", "raw_response_summary", "updated_at"])
    previous = order.fulfillment_status
    order.status = Order.Status.CANCELLED
    order.fulfillment_status = Order.FulfillmentStatus.CANCELLED
    order.save(update_fields=["status", "fulfillment_status", "updated_at"])
    OrderStatusHistory.objects.create(
        order=order, source=OrderStatusHistory.Source.SYSTEM, previous_status=previous,
        new_status=Order.FulfillmentStatus.CANCELLED, note="Toss payment cancelled",
    )
    restore_order_benefits(order)
    release_order_inventory(order)


def _cancellation_response(cancellation):
    if cancellation is None:
        return {"status": "completed"}
    return {
        "order_number": cancellation.order.order_number,
        "status": cancellation.status,
        "cancel_amount": cancellation.cancel_amount,
        "reason": cancellation.reason,
        "completed_at": cancellation.completed_at,
    }
