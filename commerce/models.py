import hashlib
import uuid

from django.db import models
from django.db.models import Q

from catalog.models import ProductListing, ProductListingVariant


def hash_guest_key(raw_key):
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class Cart(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ORDERED = "ordered", "Ordered"
        ABANDONED = "abandoned", "Abandoned"

    user = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="carts",
    )
    guest_key_hash = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status="active", user__isnull=False),
                name="unique_active_cart_per_user",
            ),
            models.UniqueConstraint(
                fields=["guest_key_hash"],
                condition=Q(status="active", guest_key_hash__isnull=False),
                name="unique_active_cart_per_guest",
            ),
        ]


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    listing = models.ForeignKey(ProductListing, on_delete=models.PROTECT, related_name="cart_items")
    listing_variant = models.ForeignKey(
        ProductListingVariant,
        on_delete=models.PROTECT,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price_snapshot = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "listing_variant"],
                name="unique_cart_listing_variant",
            )
        ]

    @property
    def line_total(self):
        return self.quantity * self.unit_price_snapshot


class Order(models.Model):
    class Status(models.TextChoices):
        PAYMENT_PENDING = "payment_pending", "Payment pending"
        PAID = "paid", "Paid"
        PAYMENT_FAILED = "payment_failed", "Payment failed"
        CANCELLED = "cancelled", "Cancelled"

    class FulfillmentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PREPARING = "preparing", "Preparing"
        READY_TO_SHIP = "ready_to_ship", "Ready to ship"
        SHIPPED = "shipped", "Shipped"
        IN_TRANSIT = "in_transit", "In transit"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        RETURNED = "returned", "Returned"

    order_number = models.CharField(max_length=40, unique=True)
    user = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    guest_order_key_hash = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PAYMENT_PENDING,
        db_index=True,
    )
    buyer_name = models.CharField(max_length=120)
    buyer_phone = models.CharField(max_length=40)
    buyer_email = models.EmailField(blank=True)
    recipient_name = models.CharField(max_length=120)
    recipient_phone = models.CharField(max_length=40)
    postal_code = models.CharField(max_length=20)
    address1 = models.CharField(max_length=240)
    address2 = models.CharField(max_length=240, blank=True)
    delivery_memo = models.CharField(max_length=240, blank=True)
    items_subtotal = models.PositiveBigIntegerField(default=0)
    shipping_fee = models.PositiveBigIntegerField(default=0)
    coupon_discount_amount = models.PositiveBigIntegerField(default=0)
    point_used_amount = models.PositiveBigIntegerField(default=0)
    payment_amount = models.PositiveBigIntegerField(default=0)
    sabangnet_status = models.CharField(max_length=30, default="not_sent", db_index=True)
    sabangnet_order_no = models.CharField(max_length=80, blank=True, db_index=True)
    sabangnet_order_status = models.CharField(max_length=80, blank=True, db_index=True)
    sabangnet_status_synced_at = models.DateTimeField(null=True, blank=True)
    fulfillment_status = models.CharField(
        max_length=30, choices=FulfillmentStatus.choices, default=FulfillmentStatus.PENDING, db_index=True
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    ordered_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def new_order_number(cls):
        return f"SEQ-{uuid.uuid4().hex[:16].upper()}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="items")
    listing = models.ForeignKey(ProductListing, null=True, blank=True, on_delete=models.PROTECT)
    listing_variant = models.ForeignKey(ProductListingVariant, null=True, blank=True, on_delete=models.PROTECT)
    listing_code_snapshot = models.CharField(max_length=80)
    listing_name_snapshot = models.CharField(max_length=240)
    listing_price_source_snapshot = models.CharField(max_length=40)
    product_name_snapshot = models.CharField(max_length=240)
    option_name_snapshot = models.CharField(max_length=240, blank=True)
    sabangnet_product_code = models.CharField(max_length=80)
    custom_product_code = models.CharField(max_length=80, blank=True)
    barcode_snapshot = models.CharField(max_length=120, blank=True)
    ordered_quantity = models.PositiveIntegerField()
    cancelled_quantity = models.PositiveIntegerField(default=0)
    returned_quantity = models.PositiveIntegerField(default=0)
    unit_price = models.PositiveBigIntegerField()
    discount_amount = models.PositiveBigIntegerField(default=0)
    line_total = models.PositiveBigIntegerField()
    review_status = models.CharField(max_length=30, default="not_available")
    created_at = models.DateTimeField(auto_now_add=True)


class PaymentAttempt(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        CONFIRMED = "confirmed", "Confirmed"
        FAILED = "failed", "Failed"
        UNKNOWN = "unknown", "Unknown"

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payment_attempts")
    provider = models.CharField(max_length=40, default="toss_payments")
    customer_key_hash = models.CharField(max_length=64, blank=True, db_index=True)
    toss_order_id = models.CharField(max_length=80, db_index=True)
    order_name = models.CharField(max_length=240)
    expected_amount = models.PositiveBigIntegerField()
    redirect_payment_key = models.CharField(max_length=200, blank=True, db_index=True)
    redirect_amount = models.PositiveBigIntegerField(null=True, blank=True)
    fail_code = models.CharField(max_length=80, blank=True)
    safe_fail_message = models.CharField(max_length=240, blank=True)
    confirm_idempotency_key = models.CharField(max_length=120, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    payload_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Payment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    attempt = models.OneToOneField(
        PaymentAttempt,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payment",
    )
    provider = models.CharField(max_length=40, default="toss_payments")
    payment_key = models.CharField(max_length=200, unique=True)
    toss_order_id = models.CharField(max_length=80, db_index=True)
    status = models.CharField(max_length=40, db_index=True)
    method = models.CharField(max_length=40, blank=True)
    total_amount = models.PositiveBigIntegerField()
    balance_amount = models.PositiveBigIntegerField()
    raw_response_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OrderStatusHistory(models.Model):
    class Source(models.TextChoices):
        SYSTEM = "system", "System"
        SABANGNET = "sabangnet", "Sabangnet"
        ADMIN = "admin", "Admin"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    source = models.CharField(max_length=20, choices=Source.choices)
    previous_status = models.CharField(max_length=30, blank=True)
    new_status = models.CharField(max_length=30)
    raw_external_status = models.CharField(max_length=80, blank=True)
    note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Shipment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="shipments")
    sabangnet_order_no = models.CharField(max_length=80, blank=True, db_index=True)
    carrier_code = models.CharField(max_length=80, blank=True)
    carrier_name = models.CharField(max_length=120, blank=True)
    tracking_number = models.CharField(max_length=160, db_index=True)
    status = models.CharField(max_length=30, blank=True, db_index=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    synced_at = models.DateTimeField(auto_now=True)
    raw_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "carrier_code", "tracking_number"],
                name="unique_order_carrier_tracking_number",
            )
        ]


class OrderCancellation(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="cancellation")
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="cancellations")
    requested_by = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="order_cancellations"
    )
    reason = models.CharField(max_length=240)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    idempotency_key = models.CharField(max_length=80, unique=True)
    cancel_amount = models.PositiveBigIntegerField()
    transaction_key = models.CharField(max_length=200, blank=True)
    failure_code = models.CharField(max_length=80, blank=True)
    failure_message = models.CharField(max_length=240, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class OrderClaim(models.Model):
    class ClaimType(models.TextChoices):
        PARTIAL_CANCEL = "partial_cancel", "Partial cancellation"
        EXCHANGE = "exchange", "Exchange"
        RETURN = "return", "Return"

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="claims")
    claim_type = models.CharField(max_length=30, choices=ClaimType.choices, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    requested_by = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="order_claims"
    )
    reason = models.CharField(max_length=240)
    detail = models.TextField(blank=True)
    refund_amount = models.PositiveBigIntegerField(default=0)
    restored_point_amount = models.PositiveBigIntegerField(default=0)
    idempotency_key = models.CharField(max_length=80, unique=True, default=uuid.uuid4)
    transaction_key = models.CharField(max_length=200, blank=True)
    failure_code = models.CharField(max_length=80, blank=True)
    failure_message = models.CharField(max_length=240, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at"]


class OrderClaimItem(models.Model):
    claim = models.ForeignKey(OrderClaim, on_delete=models.CASCADE, related_name="items")
    order_item = models.ForeignKey(OrderItem, on_delete=models.PROTECT, related_name="claim_items")
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["claim", "order_item"], name="unique_claim_order_item")
        ]
