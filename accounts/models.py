from django.conf import settings
from django.db import models


class MemberProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="member_profile")
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40, unique=True)
    identity_verified_at = models.DateTimeField(null=True, blank=True)
    terms_agreed_at = models.DateTimeField()
    marketing_agreed = models.BooleanField(default=False)
    marketing_agreed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class SocialConnection(models.Model):
    class Provider(models.TextChoices):
        KAKAO = "kakao", "카카오"
        NAVER = "naver", "네이버"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="social_connections")
    provider = models.CharField(max_length=20, choices=Provider.choices)
    provider_user_id = models.CharField(max_length=200)
    provider_email = models.EmailField(blank=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "provider"], name="unique_social_provider_per_user"),
            models.UniqueConstraint(fields=["provider", "provider_user_id"], name="unique_social_provider_identity"),
        ]

    def __str__(self):
        return f"{self.user.username} / {self.provider}"


class WishlistItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist_items")
    listing = models.ForeignKey("catalog.ProductListing", on_delete=models.CASCADE, related_name="wishlist_items")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "listing"], name="unique_user_wishlist_listing")]
        ordering = ["-created_at"]


class RecentlyViewedItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="recently_viewed_items"
    )
    guest_key_hash = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    listing = models.ForeignKey("catalog.ProductListing", on_delete=models.CASCADE, related_name="recent_views")
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "listing"], condition=models.Q(user__isnull=False), name="unique_user_recent_listing"
            ),
            models.UniqueConstraint(
                fields=["guest_key_hash", "listing"],
                condition=models.Q(guest_key_hash__isnull=False),
                name="unique_guest_recent_listing",
            ),
        ]
        ordering = ["-viewed_at"]


class ShippingAddress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shipping_addresses")
    label = models.CharField(max_length=80, default="배송지")
    recipient_name = models.CharField(max_length=120)
    recipient_phone = models.CharField(max_length=40)
    postal_code = models.CharField(max_length=20)
    address1 = models.CharField(max_length=240)
    address2 = models.CharField(max_length=240, blank=True)
    delivery_memo = models.CharField(max_length=240, blank=True)
    is_default = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"], condition=models.Q(is_default=True), name="unique_default_shipping_address_per_user"
            )
        ]
