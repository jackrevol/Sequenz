from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.generic import TemplateView
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from commerce.models import Order, Payment
from benefits.models import ShippingPolicy

from .models import ExternalApiLog, IntegrationJob, OperationsAuditLog, SabangnetOrderExport
from .toss import TossPaymentError, fetch_toss_payment


class OperationsPermission(permissions.BasePermission):
    permission = "integrations.view_operations_dashboard"

    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_staff and (
            request.user.is_superuser or request.user.has_perm(getattr(view, "required_permission", self.permission))
        ))


class OperationsPageView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "operations/dashboard.html"

    def test_func(self):
        user = self.request.user
        return user.is_staff and (user.is_superuser or user.has_perm("integrations.view_operations_dashboard"))


class OperationsDashboardView(APIView):
    permission_classes = [OperationsPermission]

    def get(self, request):
        since = timezone.now() - timedelta(days=30)
        paid = Order.objects.filter(paid_at__gte=since, status=Order.Status.PAID)
        by_status = dict(Order.objects.values_list("fulfillment_status").annotate(count=Count("id")))
        recent_orders = Order.objects.order_by("-ordered_at")[:20]
        can_view_pii = request.user.is_superuser or request.user.has_perm("integrations.view_sensitive_pii")
        return Response({
            "summary": {
                "paid_sales_30d": paid.aggregate(total=Sum("payment_amount"))["total"] or 0,
                "paid_orders_30d": paid.count(),
                "failed_exports": SabangnetOrderExport.objects.filter(status=SabangnetOrderExport.Status.FAILED).count(),
                "integration_errors_24h": ExternalApiLog.objects.filter(created_at__gte=timezone.now() - timedelta(days=1)).exclude(error_code="").count(),
                "fulfillment": by_status,
            },
            "recent_orders": [
                {
                    "order_number": order.order_number,
                    "buyer_name": order.buyer_name if can_view_pii else _mask_name(order.buyer_name),
                    "buyer_phone": order.buyer_phone if can_view_pii else _mask_phone(order.buyer_phone),
                    "status": order.status,
                    "fulfillment_status": order.fulfillment_status,
                    "payment_amount": order.payment_amount,
                    "ordered_at": order.ordered_at,
                }
                for order in recent_orders
            ],
        })


class SalesReportView(APIView):
    permission_classes = [OperationsPermission]

    def get(self, request):
        days = min(max(int(request.query_params.get("days", 30)), 1), 366)
        rows = Order.objects.filter(
            paid_at__gte=timezone.now() - timedelta(days=days), status=Order.Status.PAID
        ).annotate(day=TruncDate("paid_at")).values("day").annotate(
            order_count=Count("id"), sales=Sum("payment_amount")
        ).order_by("day")
        return Response({"results": list(rows)})


class IntegrationLogView(APIView):
    permission_classes = [OperationsPermission]

    def get(self, request):
        logs = ExternalApiLog.objects.select_related("job")[:100]
        return Response({"results": [
            {
                "id": log.id, "provider": log.provider, "operation": log.operation,
                "response_status": log.response_status, "error_code": log.error_code,
                "error_message": log.error_message, "created_at": log.created_at,
            }
            for log in logs
        ]})


class PaymentReconcileView(APIView):
    permission_classes = [OperationsPermission]
    required_permission = "integrations.reconcile_payment"

    def post(self, request, order_number):
        payment = get_object_or_404(Payment.objects.select_related("order"), order__order_number=order_number)
        job = IntegrationJob.objects.create(
            provider="toss_payments", job_type="payment_lookup", status=IntegrationJob.Status.RUNNING,
            requested_by=request.user, started_at=timezone.now(), total_count=1,
        )
        before = {"status": payment.status, "balance_amount": payment.balance_amount}
        try:
            payload = fetch_toss_payment(payment.payment_key)
        except TossPaymentError as exc:
            job.status = IntegrationJob.Status.FAILED
            job.failure_count = 1
            job.error_summary = str(exc)
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "failure_count", "error_summary", "finished_at"])
            ExternalApiLog.objects.create(
                provider="toss_payments", job=job, operation="payment_lookup", error_code=exc.code,
                error_message=str(exc), request_summary={"order_number": order_number},
            )
            return Response({"detail": str(exc), "code": exc.code}, status=status.HTTP_502_BAD_GATEWAY)
        with transaction.atomic():
            payment.status = payload.get("status", payment.status)
            payment.balance_amount = payload.get("balanceAmount", payment.balance_amount)
            payment.save(update_fields=["status", "balance_amount", "updated_at"])
            job.status = IntegrationJob.Status.SUCCEEDED
            job.success_count = 1
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "success_count", "finished_at"])
            after = {"status": payment.status, "balance_amount": payment.balance_amount}
            ExternalApiLog.objects.create(
                provider="toss_payments", job=job, operation="payment_lookup", response_status=200,
                request_summary={"order_number": order_number}, response_summary=after,
            )
            _audit(request, "payment_reconcile", "Payment", payment.pk, before, after)
        return Response(after)


class SabangnetExportRetryView(APIView):
    permission_classes = [OperationsPermission]
    required_permission = "integrations.retry_integration"

    def post(self, request, export_id):
        export = get_object_or_404(SabangnetOrderExport, pk=export_id)
        before = {"status": export.status}
        if export.status != SabangnetOrderExport.Status.FAILED:
            return Response({"detail": "실패 상태의 작업만 재시도할 수 있습니다."}, status=status.HTTP_409_CONFLICT)
        export.status = SabangnetOrderExport.Status.PENDING
        export.payload_summary = {**export.payload_summary, "retry_requested_at": timezone.now().isoformat()}
        export.save(update_fields=["status", "payload_summary", "updated_at"])
        _audit(request, "sabangnet_export_retry", "SabangnetOrderExport", export.pk, before, {"status": export.status})
        return Response({"id": export.pk, "status": export.status})


class ShippingPolicyOperationsView(APIView):
    permission_classes = [OperationsPermission]

    def get(self, request):
        policy = ShippingPolicy.objects.filter(is_default=True).first()
        return Response(_shipping_policy_data(policy))

    def patch(self, request):
        if not (request.user.is_superuser or request.user.has_perm("integrations.manage_shipping_policy")):
            return Response({"detail": "배송 정책 관리 권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        try:
            base_fee = int(request.data.get("base_fee"))
            threshold = int(request.data.get("free_shipping_threshold"))
        except (TypeError, ValueError):
            return Response({"detail": "배송비와 무료배송 기준은 0 이상의 정수여야 합니다."}, status=status.HTTP_400_BAD_REQUEST)
        if base_fee < 0 or threshold < 0:
            return Response({"detail": "배송비와 무료배송 기준은 0 이상이어야 합니다."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            policy = ShippingPolicy.objects.select_for_update().filter(is_default=True).first()
            before = _shipping_policy_data(policy)
            if policy is None:
                policy = ShippingPolicy.objects.create(
                    name=request.data.get("name", "기본 배송"), base_fee=base_fee,
                    free_shipping_threshold=threshold, is_default=True, is_active=True,
                )
            else:
                policy.name = request.data.get("name", policy.name)[:120]
                policy.base_fee = base_fee
                policy.free_shipping_threshold = threshold
                policy.is_active = bool(request.data.get("is_active", True))
                policy.save(update_fields=["name", "base_fee", "free_shipping_threshold", "is_active", "updated_at"])
            after = _shipping_policy_data(policy)
            _audit(request, "shipping_policy_update", "ShippingPolicy", policy.pk, before, after)
        return Response(after)


def _audit(request, action, target_type, target_id, before, after):
    OperationsAuditLog.objects.create(
        actor=request.user, action=action, target_type=target_type, target_id=str(target_id),
        before_summary=before, after_summary=after, ip_address=request.META.get("REMOTE_ADDR"),
    )


def _mask_name(value):
    return value[:1] + "*" * max(len(value) - 1, 1) if value else ""


def _mask_phone(value):
    digits = "".join(char for char in value if char.isdigit())
    return f"{digits[:3]}-****-{digits[-4:]}" if len(digits) >= 7 else "***"


def _shipping_policy_data(policy):
    if policy is None:
        return {"id": None, "name": "기본 배송", "base_fee": 0, "free_shipping_threshold": 0, "is_active": True}
    return {
        "id": policy.pk, "name": policy.name, "base_fee": policy.base_fee,
        "free_shipping_threshold": policy.free_shipping_threshold, "is_active": policy.is_active,
    }
