from django.urls import path

from .views import IntegrationLogView, OperationsDashboardView, OperationsPageView, PaymentReconcileView, SabangnetExportRetryView, SalesReportView, ShippingPolicyOperationsView


urlpatterns = [
    path("", OperationsPageView.as_view(), name="operations-page"),
    path("api/dashboard/", OperationsDashboardView.as_view(), name="operations-dashboard"),
    path("api/sales/", SalesReportView.as_view(), name="operations-sales"),
    path("api/logs/", IntegrationLogView.as_view(), name="operations-logs"),
    path("api/payments/<str:order_number>/reconcile/", PaymentReconcileView.as_view(), name="payment-reconcile"),
    path("api/sabangnet/exports/<int:export_id>/retry/", SabangnetExportRetryView.as_view(), name="sabangnet-export-retry"),
    path("api/shipping-policy/", ShippingPolicyOperationsView.as_view(), name="operations-shipping-policy"),
]
