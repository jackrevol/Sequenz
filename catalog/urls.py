from django.urls import path

from .views import BrandListView, CategoryListView, ProductFilterView, ProductListingDetailView, ProductListingListView, SearchKeywordView


urlpatterns = [
    path("brands/", BrandListView.as_view(), name="brand-list"),
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("listings/", ProductListingListView.as_view(), name="listing-list"),
    path("listings/<int:pk>/", ProductListingDetailView.as_view(), name="listing-detail"),
    path("filters/", ProductFilterView.as_view(), name="product-filters"),
    path("search-keywords/", SearchKeywordView.as_view(), name="search-keywords"),
]
