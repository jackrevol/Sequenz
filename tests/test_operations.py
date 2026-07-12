from unittest.mock import patch

import pytest

from commerce.models import Order, Payment
from integrations.models import OperationsAuditLog, SabangnetOrderExport
from benefits.models import ShippingPolicy


@pytest.fixture
def operations_order(db):
    order = Order.objects.create(
        order_number="SEQ-OPS-1", status=Order.Status.PAID, buyer_name="Operations User",
        buyer_phone="01012345678", recipient_name="Receiver", recipient_phone="01012345678",
        postal_code="06000", address1="Seoul", payment_amount=50000,
    )
    payment = Payment.objects.create(
        order=order, payment_key="ops-payment", toss_order_id=order.order_number,
        status="DONE", total_amount=50000, balance_amount=50000,
    )
    export = SabangnetOrderExport.objects.create(order=order, status=SabangnetOrderExport.Status.FAILED)
    return order, payment, export


@pytest.mark.django_db
def test_operations_dashboard_requires_staff_and_returns_metrics(api_client, django_user_model, operations_order):
    user = django_user_model.objects.create_user("normal", password="password")
    api_client.force_login(user)
    assert api_client.get("/operations/api/dashboard/").status_code == 403

    admin = django_user_model.objects.create_superuser("ops-admin", "ops@example.com", "password")
    api_client.force_login(admin)
    response = api_client.get("/operations/api/dashboard/")

    assert response.status_code == 200
    assert response.json()["summary"]["failed_exports"] == 1
    assert response.json()["recent_orders"][0]["buyer_phone"] == "01012345678"


@pytest.mark.django_db
def test_payment_reconcile_and_sabangnet_retry_are_audited(api_client, django_user_model, operations_order):
    order, payment, export = operations_order
    admin = django_user_model.objects.create_superuser("ops-action", "action@example.com", "password")
    api_client.force_login(admin)
    with patch("integrations.views.fetch_toss_payment", return_value={"status": "PARTIAL_CANCELED", "balanceAmount": 20000}):
        reconciled = api_client.post(f"/operations/api/payments/{order.order_number}/reconcile/", {}, format="json")
    retried = api_client.post(f"/operations/api/sabangnet/exports/{export.id}/retry/", {}, format="json")
    policy = api_client.patch(
        "/operations/api/shipping-policy/",
        {"name": "기본 배송", "base_fee": 3000, "free_shipping_threshold": 70000},
        format="json",
    )

    assert reconciled.status_code == 200
    payment.refresh_from_db()
    assert payment.balance_amount == 20000
    assert retried.status_code == 200
    assert policy.status_code == 200
    assert ShippingPolicy.objects.get(is_default=True).free_shipping_threshold == 70000
    export.refresh_from_db()
    assert export.status == SabangnetOrderExport.Status.PENDING
    assert set(OperationsAuditLog.objects.values_list("action", flat=True)) == {
        "payment_reconcile", "sabangnet_export_retry", "shipping_policy_update",
    }
