from django.urls import path

from .views import ProductDetailPageView, StorefrontPageView, StorefrontView


urlpatterns = [
    path("cart/", StorefrontPageView.as_view(extra_context={"page_kind": "cart", "page_title": "장바구니"}), name="cart-page"),
    path("checkout/", StorefrontPageView.as_view(extra_context={"page_kind": "checkout", "page_title": "주문/결제"}), name="checkout-page"),
    path("account/", StorefrontPageView.as_view(extra_context={"page_kind": "account", "page_title": "마이페이지"}), name="account-page"),
    path("support/", StorefrontPageView.as_view(extra_context={"page_kind": "support", "page_title": "고객센터"}), name="support-page"),
    path("orders/<str:order_number>/", StorefrontPageView.as_view(extra_context={"page_kind": "order", "page_title": "주문상세"}), name="order-page"),
    path("content/<str:content_type>/<slug:slug>/", StorefrontPageView.as_view(extra_context={"page_kind": "content", "page_title": "콘텐츠"}), name="content-page"),
    path("products/<int:pk>/", ProductDetailPageView.as_view(), name="product-detail-page"),
    path("", StorefrontView.as_view(), name="storefront"),
]
