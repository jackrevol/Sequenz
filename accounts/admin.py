from django.contrib import admin

from .models import MemberProfile, RecentlyViewedItem, ShippingAddress, SocialConnection, WishlistItem


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "phone", "marketing_agreed", "identity_verified_at", "created_at")
    list_filter = ("marketing_agreed", "identity_verified_at")
    search_fields = ("user__username", "user__email", "name", "phone")


@admin.register(SocialConnection)
class SocialConnectionAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "provider_email", "connected_at", "last_login_at")
    list_filter = ("provider",)
    search_fields = ("user__username", "provider_user_id", "provider_email")
    readonly_fields = ("provider_user_id", "connected_at", "last_login_at")


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("user", "listing", "created_at")
    search_fields = ("user__username", "listing__display_name")


@admin.register(RecentlyViewedItem)
class RecentlyViewedItemAdmin(admin.ModelAdmin):
    list_display = ("user", "listing", "viewed_at")
    search_fields = ("user__username", "listing__display_name")
    readonly_fields = ("guest_key_hash",)


@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "recipient_name", "postal_code", "is_default", "updated_at")
    list_filter = ("is_default",)
    search_fields = ("user__username", "recipient_name", "recipient_phone", "address1", "address2")
