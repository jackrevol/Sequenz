from django.urls import path

from .views import StorefrontView


urlpatterns = [path("", StorefrontView.as_view(), name="storefront")]
