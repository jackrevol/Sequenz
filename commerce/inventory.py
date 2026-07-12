from django.db import transaction

from catalog.models import ProductVariant

from .models import Order


class InventoryReservationError(Exception):
    pass


@transaction.atomic
def reserve_order_inventory(order, quantities):
    if order.inventory_reservation_status != Order.InventoryReservationStatus.NONE:
        return
    variants = {
        variant.pk: variant for variant in ProductVariant.objects.select_for_update().filter(pk__in=quantities)
    }
    for variant_id, quantity in quantities.items():
        variant = variants.get(variant_id)
        if variant is None or variant.available_quantity < quantity:
            raise InventoryReservationError("주문 가능한 재고가 부족합니다.")
    for variant_id, quantity in quantities.items():
        variant = variants[variant_id]
        variant.reserved_quantity += quantity
        variant.save(update_fields=["reserved_quantity", "updated_at"])
    order.inventory_reservation_status = Order.InventoryReservationStatus.RESERVED
    order.save(update_fields=["inventory_reservation_status", "updated_at"])


@transaction.atomic
def consume_order_inventory(order):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.inventory_reservation_status != Order.InventoryReservationStatus.RESERVED:
        return False
    for item in order.items.select_related("listing_variant__variant"):
        if item.listing_variant_id is None:
            continue
        variant = ProductVariant.objects.select_for_update().get(pk=item.listing_variant.variant_id)
        quantity = item.ordered_quantity - item.cancelled_quantity
        variant.reserved_quantity = max(variant.reserved_quantity - quantity, 0)
        variant.save(update_fields=["reserved_quantity", "updated_at"])
    order.inventory_reservation_status = Order.InventoryReservationStatus.CONSUMED
    order.save(update_fields=["inventory_reservation_status", "updated_at"])
    return True


@transaction.atomic
def release_order_inventory(order):
    order = Order.objects.select_for_update().get(pk=order.pk)
    state = order.inventory_reservation_status
    if state not in {Order.InventoryReservationStatus.RESERVED, Order.InventoryReservationStatus.CONSUMED}:
        return False
    for item in order.items.select_related("listing_variant__variant"):
        if item.listing_variant_id is None:
            continue
        variant = ProductVariant.objects.select_for_update().get(pk=item.listing_variant.variant_id)
        quantity = item.ordered_quantity - item.cancelled_quantity
        if state == Order.InventoryReservationStatus.RESERVED:
            variant.reserved_quantity = max(variant.reserved_quantity - quantity, 0)
            fields = ["reserved_quantity", "updated_at"]
        else:
            variant.stock_quantity += quantity
            fields = ["stock_quantity", "updated_at"]
        variant.save(update_fields=fields)
    order.inventory_reservation_status = Order.InventoryReservationStatus.RELEASED
    order.save(update_fields=["inventory_reservation_status", "updated_at"])
    return True
