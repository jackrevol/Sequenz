from django.urls import path

from .views import ProductListingDetailView, ProductListingListView


urlpatterns = [
    path("listings/", ProductListingListView.as_view(), name="listing-list"),
    path("listings/<int:pk>/", ProductListingDetailView.as_view(), name="listing-detail"),
]
