from decimal import Decimal, ROUND_DOWN

from django.db import transaction
from django.utils import timezone

from .models import Coupon, CouponUsage, MemberBenefitAccount, MemberCoupon, MemberTier, PointLedger, ShippingPolicy


class BenefitValidationError(Exception):
    pass


def shipping_fee_for(subtotal):
    policy = ShippingPolicy.objects.filter(is_active=True, is_default=True).first()
    if policy is None:
        return 0
    if policy.free_shipping_threshold and subtotal >= policy.free_shipping_threshold:
        return 0
    return policy.base_fee


def quote_member_benefits(user, subtotal, coupon_code="", point_to_use=0):
    shipping_fee = shipping_fee_for(subtotal)
    coupon_discount = 0
    member_coupon = None
    if coupon_code:
        if not user or not user.is_authenticated:
            raise BenefitValidationError("쿠폰은 회원만 사용할 수 있습니다.")
        member_coupon = MemberCoupon.objects.select_related("coupon").filter(
            user=user, coupon__code=coupon_code, status=MemberCoupon.Status.AVAILABLE
        ).first()
        if member_coupon is None:
            raise BenefitValidationError("사용 가능한 쿠폰이 아닙니다.")
        coupon_discount, shipping_fee = _coupon_discount(member_coupon.coupon, subtotal, shipping_fee)
    point_to_use = int(point_to_use or 0)
    if point_to_use < 0:
        raise BenefitValidationError("사용 적립금은 0 이상이어야 합니다.")
    account = None
    if point_to_use:
        if not user or not user.is_authenticated:
            raise BenefitValidationError("적립금은 회원만 사용할 수 있습니다.")
        account, _ = MemberBenefitAccount.objects.get_or_create(user=user)
        if point_to_use > account.point_balance:
            raise BenefitValidationError("보유 적립금이 부족합니다.")
    payable_before_points = max(subtotal + shipping_fee - coupon_discount, 0)
    if point_to_use > payable_before_points:
        raise BenefitValidationError("결제금액보다 많은 적립금을 사용할 수 없습니다.")
    if payable_before_points - point_to_use <= 0:
        raise BenefitValidationError("최종 결제금액은 1원 이상이어야 합니다.")
    return {
        "shipping_fee": shipping_fee,
        "coupon_discount_amount": coupon_discount,
        "point_used_amount": point_to_use,
        "payment_amount": payable_before_points - point_to_use,
        "member_coupon": member_coupon,
        "benefit_account": account,
    }


@transaction.atomic
def apply_order_benefits(order, quote):
    now = timezone.now()
    member_coupon = quote.get("member_coupon")
    if member_coupon:
        locked = MemberCoupon.objects.select_for_update().get(pk=member_coupon.pk)
        if locked.status != MemberCoupon.Status.AVAILABLE:
            raise BenefitValidationError("쿠폰이 이미 사용되었습니다.")
        locked.status = MemberCoupon.Status.USED
        locked.used_at = now
        locked.save(update_fields=["status", "used_at"])
        CouponUsage.objects.create(
            member_coupon=locked, order=order, discount_amount=quote["coupon_discount_amount"]
        )
    point_amount = quote["point_used_amount"]
    if point_amount:
        account = MemberBenefitAccount.objects.select_for_update().get(pk=quote["benefit_account"].pk)
        if account.point_balance < point_amount:
            raise BenefitValidationError("보유 적립금이 부족합니다.")
        account.point_balance -= point_amount
        account.save(update_fields=["point_balance", "updated_at"])
        PointLedger.objects.create(
            account=account, order=order, amount=-point_amount, balance_after=account.point_balance,
            reason=PointLedger.Reason.ORDER_USE,
        )


@transaction.atomic
def restore_order_benefits(order):
    now = timezone.now()
    usage = CouponUsage.objects.select_for_update().filter(order=order, restored_at__isnull=True).select_related(
        "member_coupon"
    ).first()
    if usage:
        usage.member_coupon.status = MemberCoupon.Status.AVAILABLE
        usage.member_coupon.used_at = None
        usage.member_coupon.save(update_fields=["status", "used_at"])
        usage.restored_at = now
        usage.save(update_fields=["restored_at"])
    already_restored = sum(
        PointLedger.objects.filter(order=order, reason=PointLedger.Reason.CANCEL_RESTORE)
        .values_list("amount", flat=True)
    )
    remaining_points = max(order.point_used_amount - already_restored, 0)
    if order.user_id and remaining_points:
        account, _ = MemberBenefitAccount.objects.select_for_update().get_or_create(user=order.user)
        account.point_balance += remaining_points
        account.save(update_fields=["point_balance", "updated_at"])
        PointLedger.objects.create(
            account=account,
            order=order,
            amount=remaining_points,
            balance_after=account.point_balance,
            reason=PointLedger.Reason.CANCEL_RESTORE,
        )


@transaction.atomic
def complete_delivered_order_benefits(order):
    if not order.user_id:
        return None
    account, _ = MemberBenefitAccount.objects.select_for_update().get_or_create(user=order.user)
    if PointLedger.objects.filter(order=order, reason=PointLedger.Reason.ORDER_EARN).exists():
        return account
    account.lifetime_purchase_amount += order.payment_amount
    account.completed_order_count += 1
    account.tier = _eligible_tier(account.lifetime_purchase_amount, account.completed_order_count)
    earn_rate = account.tier.point_earn_rate if account.tier else Decimal("0")
    earned = int((Decimal(order.payment_amount) * earn_rate / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_DOWN))
    account.point_balance += earned
    account.save(
        update_fields=["lifetime_purchase_amount", "completed_order_count", "tier", "point_balance", "updated_at"]
    )
    PointLedger.objects.create(
        account=account,
        order=order,
        amount=earned,
        balance_after=account.point_balance,
        reason=PointLedger.Reason.ORDER_EARN,
    )
    return account


@transaction.atomic
def reverse_delivered_order_benefits(order):
    if not order.user_id:
        return None
    earned_ledger = PointLedger.objects.filter(order=order, reason=PointLedger.Reason.ORDER_EARN).first()
    if earned_ledger is None or PointLedger.objects.filter(
        order=order, reason=PointLedger.Reason.ORDER_EARN_REVERSAL
    ).exists():
        return MemberBenefitAccount.objects.filter(user=order.user).first()
    account = MemberBenefitAccount.objects.select_for_update().get(user=order.user)
    account.lifetime_purchase_amount = max(account.lifetime_purchase_amount - order.payment_amount, 0)
    account.completed_order_count = max(account.completed_order_count - 1, 0)
    account.point_balance -= earned_ledger.amount
    account.tier = _eligible_tier(account.lifetime_purchase_amount, account.completed_order_count)
    account.save(
        update_fields=["lifetime_purchase_amount", "completed_order_count", "point_balance", "tier", "updated_at"]
    )
    PointLedger.objects.create(
        account=account, order=order, amount=-earned_ledger.amount,
        balance_after=account.point_balance, reason=PointLedger.Reason.ORDER_EARN_REVERSAL,
        description="반품 완료에 따른 배송완료 적립 회수",
    )
    return account


def _eligible_tier(purchase_amount, order_count):
    eligible = None
    for tier in MemberTier.objects.filter(is_active=True).order_by("minimum_purchase_amount", "minimum_order_count"):
        if purchase_amount >= tier.minimum_purchase_amount and order_count >= tier.minimum_order_count:
            eligible = tier
    return eligible


def _coupon_discount(coupon, subtotal, shipping_fee):
    now = timezone.now()
    if not coupon.is_active or (coupon.starts_at and coupon.starts_at > now) or (coupon.ends_at and coupon.ends_at < now):
        raise BenefitValidationError("쿠폰 사용기간이 아닙니다.")
    if subtotal < coupon.minimum_order_amount:
        raise BenefitValidationError("쿠폰 최소 주문금액을 충족하지 않습니다.")
    if coupon.discount_type == Coupon.DiscountType.FREE_SHIPPING:
        return 0, 0
    if coupon.discount_type == Coupon.DiscountType.FIXED:
        discount = coupon.discount_value
    else:
        discount = int((Decimal(subtotal) * Decimal(coupon.discount_value) / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_DOWN))
    if coupon.maximum_discount_amount is not None:
        discount = min(discount, coupon.maximum_discount_amount)
    return min(discount, subtotal), shipping_fee
