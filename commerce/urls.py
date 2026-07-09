from django.urls import path

from .views import CartItemView, OrderView


urlpatterns = [
    path("cart/items/", CartItemView.as_view(), name="cart-items"),
    path("orders/", OrderView.as_view(), name="orders"),
]
