from django.urls import path

from .views import (
    LoginView, LogoutView, MeView, RecentlyViewedView, RegistrationView, ShippingAddressDetailView,
    ShippingAddressListCreateView,
    SocialConnectionStartView, WishlistDetailView, WishlistView,
)


urlpatterns = [
    path("register/", RegistrationView.as_view(), name="account-register"),
    path("login/", LoginView.as_view(), name="account-login"),
    path("logout/", LogoutView.as_view(), name="account-logout"),
    path("me/", MeView.as_view(), name="account-me"),
    path("social/<str:provider>/connect/", SocialConnectionStartView.as_view(), name="social-connect"),
    path("wishlist/", WishlistView.as_view(), name="wishlist"),
    path("wishlist/<int:listing_id>/", WishlistDetailView.as_view(), name="wishlist-detail"),
    path("recently-viewed/", RecentlyViewedView.as_view(), name="recently-viewed"),
    path("addresses/", ShippingAddressListCreateView.as_view(), name="shipping-address-list"),
    path("addresses/<int:pk>/", ShippingAddressDetailView.as_view(), name="shipping-address-detail"),
]
