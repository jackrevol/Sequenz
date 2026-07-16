from django.conf import settings
from django.db import models
from django.db.models import Q


class ShippingPolicy(models.Model):
    name = models.CharField(max_length=120)
    base_fee = models.PositiveBigIntegerField(default=0)
    free_shipping_threshold = models.PositiveBigIntegerField(default=0)
    is_default = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"], condition=Q(is_default=True), name="unique_default_shipping_policy"
            )
        ]

    def __str__(self):
        return self.name


class MemberTier(models.Model):
    name = models.CharField(max_length=80)
    code = models.SlugField(max_length=80, unique=True)
    minimum_purchase_amount = models.PositiveBigIntegerField(default=0)
    minimum_order_count = models.PositiveIntegerField(default=0)
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    point_earn_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "minimum_purchase_amount"]

    def __str__(self):
        return self.name


class MemberBenefitAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="benefit_account")
    tier = models.ForeignKey(MemberTier, null=True, blank=True, on_delete=models.SET_NULL, related_name="members")
    point_balance = models.BigIntegerField(default=0)
    lifetime_purchase_amount = models.PositiveBigIntegerField(default=0)
    completed_order_count = models.PositiveIntegerField(default=0)
    tier_expires_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        FIXED = "fixed", "정액 할인"
        PERCENT = "percent", "정률 할인"
        FREE_SHIPPING = "free_shipping", "무료배송"

    name = models.CharField(max_length=160)
    code = models.CharField(max_length=80, unique=True)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.PositiveBigIntegerField(default=0)
    minimum_order_amount = models.PositiveBigIntegerField(default=0)
    maximum_discount_amount = models.PositiveBigIntegerField(null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class MemberCoupon(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "사용 가능"
        USED = "used", "사용 완료"
        EXPIRED = "expired", "기간 만료"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="member_coupons")
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="issued_coupons")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "coupon"], name="unique_member_coupon")]


class CouponUsage(models.Model):
    member_coupon = models.OneToOneField(MemberCoupon, on_delete=models.PROTECT, related_name="usage")
    order = models.OneToOneField("commerce.Order", on_delete=models.PROTECT, related_name="coupon_usage")
    discount_amount = models.PositiveBigIntegerField()
    restored_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PointLedger(models.Model):
    class Reason(models.TextChoices):
        ORDER_USE = "order_use", "주문 사용"
        ORDER_EARN = "order_earn", "주문 적립"
        ORDER_EARN_REVERSAL = "order_earn_reversal", "주문 적립 취소"
        REVIEW_EARN = "review_earn", "리뷰 적립"
        CANCEL_RESTORE = "cancel_restore", "취소 복원"
        ADMIN = "admin", "관리자 조정"
        EXPIRE = "expire", "유효기간 만료"

    account = models.ForeignKey(MemberBenefitAccount, on_delete=models.PROTECT, related_name="point_ledger")
    order = models.ForeignKey("commerce.Order", null=True, blank=True, on_delete=models.PROTECT, related_name="point_ledger")
    amount = models.BigIntegerField()
    balance_after = models.BigIntegerField()
    reason = models.CharField(max_length=30, choices=Reason.choices)
    description = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
