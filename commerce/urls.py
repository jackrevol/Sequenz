from django.urls import path

from .views import CartItemView, OrderView, TossPaymentConfirmView


urlpatterns = [
    path("cart/items/", CartItemView.as_view(), name="cart-items"),
    path("orders/", OrderView.as_view(), name="orders"),
    path("payments/toss/confirm/", TossPaymentConfirmView.as_view(), name="toss-payment-confirm"),
]
