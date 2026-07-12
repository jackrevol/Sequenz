from django.urls import path

from .views import CollectionDetailView, CollectionListView, HomeBannerListView


urlpatterns = [
    path("banners/", HomeBannerListView.as_view(), name="home-banners"),
    path("collections/", CollectionListView.as_view(), name="collection-list"),
    path("collections/<slug:slug>/", CollectionDetailView.as_view(), name="collection-detail"),
]
