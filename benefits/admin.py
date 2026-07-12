from django.contrib import admin

from .models import Coupon, CouponUsage, MemberBenefitAccount, MemberCoupon, MemberTier, PointLedger, ShippingPolicy


@admin.register(ShippingPolicy)
class ShippingPolicyAdmin(admin.ModelAdmin):
    list_display = ("name", "base_fee", "free_shipping_threshold", "is_default", "is_active", "updated_at")
    list_editable = ("is_default", "is_active")


@admin.register(MemberTier)
class MemberTierAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "minimum_purchase_amount", "minimum_order_count", "discount_rate", "point_earn_rate", "is_active")
    list_editable = ("is_active",)


@admin.register(MemberBenefitAccount)
class MemberBenefitAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "tier", "point_balance", "lifetime_purchase_amount", "completed_order_count", "updated_at")
    search_fields = ("user__username", "user__email")


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "discount_type", "discount_value", "minimum_order_amount", "is_active", "starts_at", "ends_at")
    list_filter = ("discount_type", "is_active")
    search_fields = ("name", "code")


@admin.register(MemberCoupon)
class MemberCouponAdmin(admin.ModelAdmin):
    list_display = ("user", "coupon", "status", "issued_at", "used_at")
    list_filter = ("status",)
    search_fields = ("user__username", "coupon__code")


admin.site.register(CouponUsage)
admin.site.register(PointLedger)
