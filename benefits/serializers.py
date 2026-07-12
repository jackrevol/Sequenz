from rest_framework import serializers

from .models import Coupon, MemberBenefitAccount, MemberCoupon, MemberTier, PointLedger, ShippingPolicy


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ["name", "code", "discount_type", "discount_value", "minimum_order_amount", "maximum_discount_amount", "starts_at", "ends_at"]


class MemberCouponSerializer(serializers.ModelSerializer):
    coupon = CouponSerializer(read_only=True)

    class Meta:
        model = MemberCoupon
        fields = ["id", "status", "issued_at", "used_at", "coupon"]


class MemberBenefitSerializer(serializers.ModelSerializer):
    tier_name = serializers.CharField(source="tier.name", default="일반 회원")

    class Meta:
        model = MemberBenefitAccount
        fields = ["tier_name", "point_balance", "lifetime_purchase_amount", "completed_order_count", "tier_expires_at"]


class PointLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = PointLedger
        fields = ["id", "amount", "balance_after", "reason", "description", "created_at"]
