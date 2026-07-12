from django.contrib import admin

from .models import Cart, CartItem, Order, OrderCancellation, OrderItem, OrderStatusHistory, Payment, PaymentAttempt, Shipment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "listing_name_snapshot", "product_name_snapshot", "option_name_snapshot",
        "ordered_quantity", "unit_price", "line_total",
    )


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ("source", "previous_status", "new_status", "raw_external_status", "note", "created_at")


class ShipmentInline(admin.TabularInline):
    model = Shipment
    extra = 0
    can_delete = False
    readonly_fields = (
        "sabangnet_order_no", "carrier_code", "carrier_name", "tracking_number", "status",
        "shipped_at", "delivered_at", "synced_at", "raw_summary", "created_at",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "status", "fulfillment_status", "buyer_name", "recipient_name", "payment_amount", "sabangnet_order_status", "ordered_at")
    list_filter = ("status", "fulfillment_status", "sabangnet_status", "ordered_at")
    search_fields = ("order_number", "buyer_name", "buyer_phone", "recipient_name", "recipient_phone")
    readonly_fields = ("order_number", "items_subtotal", "payment_amount", "paid_at", "ordered_at", "created_at", "updated_at")
    inlines = (OrderItemInline, ShipmentInline, OrderStatusHistoryInline)
    date_hierarchy = "ordered_at"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("payment_key", "order", "status", "method", "total_amount", "created_at")
    list_filter = ("status", "method", "provider")
    search_fields = ("payment_key", "toss_order_id", "order__order_number")
    readonly_fields = tuple(field.name for field in Payment._meta.fields)


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ("toss_order_id", "status", "expected_amount", "redirect_amount", "created_at")
    list_filter = ("status", "provider")
    search_fields = ("toss_order_id", "redirect_payment_key")
    readonly_fields = tuple(field.name for field in PaymentAttempt._meta.fields)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "created_at", "updated_at")
    list_filter = ("status",)
    readonly_fields = ("guest_key_hash",)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "listing", "quantity", "unit_price_snapshot", "updated_at")


@admin.register(OrderCancellation)
class OrderCancellationAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "cancel_amount", "reason", "requested_at", "completed_at")
    list_filter = ("status", "requested_at")
    search_fields = ("order__order_number", "payment__payment_key", "reason", "transaction_key")
    readonly_fields = tuple(field.name for field in OrderCancellation._meta.fields)
