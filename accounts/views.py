from django.contrib.auth import login, logout
from django.db import transaction
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import ProductListing
from catalog.serializers import ProductListingSerializer
from commerce.models import hash_guest_key

from .models import RecentlyViewedItem, ShippingAddress, WishlistItem
from .serializers import LoginSerializer, MemberSerializer, RegistrationSerializer, ShippingAddressSerializer


class RegistrationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        _claim_guest_cart(request, user)
        return Response(MemberSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        login(request, user)
        _claim_guest_cart(request, user)
        return Response(MemberSerializer(user).data)


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(MemberSerializer(request.user).data)


class SocialConnectionStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, provider):
        if provider not in {"kakao", "naver"}:
            return Response({"detail": "지원하지 않는 소셜 서비스입니다."}, status=status.HTTP_404_NOT_FOUND)
        # TODO(social-oauth): Generate a signed state tied to request.user,
        # redirect to the provider, verify callback state, and create a
        # SocialConnection. Never create a new User from a social callback.
        return Response(
            {"detail": "소셜 계정 연결은 OAuth 자격 증명 설정 후 활성화됩니다.", "provider": provider},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


class WishlistView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        listings = ProductListing.objects.filter(wishlist_items__user=request.user).select_related(
            "product", "product__brand", "product__category"
        ).prefetch_related("variants__variant")
        return Response({"results": ProductListingSerializer(listings, many=True).data})

    def post(self, request):
        listing = _active_listing(request.data.get("listing_id"))
        if listing is None:
            return Response({"detail": "Unknown listing."}, status=status.HTTP_404_NOT_FOUND)
        item, created = WishlistItem.objects.get_or_create(user=request.user, listing=listing)
        return Response({"listing_id": item.listing_id, "created": created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class WishlistDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, listing_id):
        WishlistItem.objects.filter(user=request.user, listing_id=listing_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecentlyViewedView(APIView):
    def get(self, request):
        identity = _recent_identity(request)
        if identity is None:
            return Response({"detail": "Login or X-Guest-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        views = RecentlyViewedItem.objects.filter(**identity).select_related(
            "listing__product", "listing__product__brand", "listing__product__category"
        ).prefetch_related("listing__variants__variant")[:30]
        return Response({"results": ProductListingSerializer([view.listing for view in views], many=True).data})

    def post(self, request):
        identity = _recent_identity(request)
        if identity is None:
            return Response({"detail": "Login or X-Guest-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        listing = _active_listing(request.data.get("listing_id"))
        if listing is None:
            return Response({"detail": "Unknown listing."}, status=status.HTTP_404_NOT_FOUND)
        item, _ = RecentlyViewedItem.objects.update_or_create(listing=listing, **identity, defaults={})
        item.save(update_fields=["viewed_at"])
        return Response({"listing_id": listing.id}, status=status.HTTP_201_CREATED)


class ShippingAddressListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ShippingAddressSerializer

    def get_queryset(self):
        return ShippingAddress.objects.filter(user=self.request.user)

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "request": self.request}


class ShippingAddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ShippingAddressSerializer

    def get_queryset(self):
        return ShippingAddress.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        was_default = instance.is_default
        user = instance.user
        instance.delete()
        if was_default:
            replacement = user.shipping_addresses.order_by("-updated_at").first()
            if replacement:
                replacement.is_default = True
                replacement.save(update_fields=["is_default", "updated_at"])


def _active_listing(listing_id):
    try:
        return ProductListing.objects.get(pk=listing_id, status=ProductListing.Status.ACTIVE)
    except (ProductListing.DoesNotExist, TypeError, ValueError):
        return None


def _recent_identity(request):
    if request.user.is_authenticated:
        return {"user": request.user, "guest_key_hash": None}
    raw_key = request.headers.get("X-Guest-Key", "")
    if raw_key:
        return {"user": None, "guest_key_hash": hash_guest_key(raw_key)}
    return None


@transaction.atomic
def _claim_guest_cart(request, user):
    from commerce.models import Cart, CartItem, hash_guest_key

    raw_guest_key = request.headers.get("X-Guest-Key", "")
    if not raw_guest_key:
        return None
    guest_hash = hash_guest_key(raw_guest_key)
    guest_cart = Cart.objects.select_for_update().filter(
        guest_key_hash=guest_hash,
        status=Cart.Status.ACTIVE,
    ).first()
    if guest_cart is None:
        return None
    user_cart = Cart.objects.select_for_update().filter(user=user, status=Cart.Status.ACTIVE).first()
    if user_cart is None:
        guest_cart.user = user
        guest_cart.guest_key_hash = None
        guest_cart.save(update_fields=["user", "guest_key_hash", "updated_at"])
        return guest_cart
    if user_cart.pk == guest_cart.pk:
        return user_cart
    for guest_item in guest_cart.items.select_related("listing_variant").all():
        existing = user_cart.items.filter(listing_variant=guest_item.listing_variant).first()
        if existing:
            max_stock = guest_item.listing_variant.variant.stock_quantity
            existing.quantity = min(existing.quantity + guest_item.quantity, max_stock)
            existing.save(update_fields=["quantity", "updated_at"])
        else:
            CartItem.objects.filter(pk=guest_item.pk).update(cart=user_cart)
    guest_cart.status = Cart.Status.ABANDONED
    guest_cart.save(update_fields=["status", "updated_at"])
    return user_cart
