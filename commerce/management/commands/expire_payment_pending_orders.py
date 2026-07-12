from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from commerce.inventory import release_order_inventory
from commerce.models import Order


class Command(BaseCommand):
    help = "만료된 결제대기 주문을 실패 처리하고 예약 재고를 복원합니다."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(minutes=settings.PAYMENT_PENDING_TIMEOUT_MINUTES)
        order_ids = Order.objects.filter(
            status=Order.Status.PAYMENT_PENDING,
            inventory_reservation_status=Order.InventoryReservationStatus.RESERVED,
            created_at__lt=cutoff,
        ).values_list("pk", flat=True)
        expired = 0
        for order_id in order_ids.iterator():
            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=order_id)
                if order.status != Order.Status.PAYMENT_PENDING:
                    continue
                release_order_inventory(order)
                order.status = Order.Status.PAYMENT_FAILED
                order.save(update_fields=["status", "updated_at"])
                expired += 1
        self.stdout.write(self.style.SUCCESS(f"{expired}건의 결제대기 주문을 만료 처리했습니다."))
