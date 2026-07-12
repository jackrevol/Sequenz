from django.urls import path

from .views import ProductDetailPageView, StorefrontView


urlpatterns = [
    path("products/<int:pk>/", ProductDetailPageView.as_view(), name="product-detail-page"),
    path("", StorefrontView.as_view(), name="storefront"),
]
