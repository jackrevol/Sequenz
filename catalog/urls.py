from django.urls import path

from .views import BrandListView, CategoryListView, ProductListingDetailView, ProductListingListView


urlpatterns = [
    path("brands/", BrandListView.as_view(), name="brand-list"),
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("listings/", ProductListingListView.as_view(), name="listing-list"),
    path("listings/<int:pk>/", ProductListingDetailView.as_view(), name="listing-detail"),
]
