from django.urls import path

from .views import MyBenefitsView, PointLedgerListView, ShippingPolicyView


urlpatterns = [
    path("mine/", MyBenefitsView.as_view(), name="my-benefits"),
    path("points/", PointLedgerListView.as_view(), name="point-ledger"),
    path("shipping-policy/", ShippingPolicyView.as_view(), name="shipping-policy"),
]
