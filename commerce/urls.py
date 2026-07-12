from django.urls import path

from .views import CartBenefitQuoteView, CartItemDetailView, CartItemView, GuestOrderLookupView, MemberOrderListView, OrderCancellationView, OrderClaimView, OrderDetailView, OrderView, TossPaymentConfirmView, TossPaymentPrepareView


urlpatterns = [
    path("cart/items/", CartItemView.as_view(), name="cart-items"),
    path("cart/items/<int:pk>/", CartItemDetailView.as_view(), name="cart-item-detail"),
    path("cart/benefit-quote/", CartBenefitQuoteView.as_view(), name="cart-benefit-quote"),
    path("orders/", OrderView.as_view(), name="orders"),
    path("orders/mine/", MemberOrderListView.as_view(), name="member-orders"),
    path("orders/guest-lookup/", GuestOrderLookupView.as_view(), name="guest-order-lookup"),
    path("orders/<str:order_number>/", OrderDetailView.as_view(), name="order-detail"),
    path("orders/<str:order_number>/cancel/", OrderCancellationView.as_view(), name="order-cancel"),
    path("orders/<str:order_number>/claims/", OrderClaimView.as_view(), name="order-claims"),
    path("payments/toss/confirm/", TossPaymentConfirmView.as_view(), name="toss-payment-confirm"),
    path("payments/toss/prepare/<str:order_number>/", TossPaymentPrepareView.as_view(), name="toss-payment-prepare"),
]
