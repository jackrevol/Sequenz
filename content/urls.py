from django.urls import path

from .views import CollectionDetailView, CollectionListView, FAQListView, HomeBannerListView, LookbookDetailView, LookbookListView, NoticeListView, PolicyPageDetailView, PromotionDetailView, PromotionListView


urlpatterns = [
    path("banners/", HomeBannerListView.as_view(), name="home-banners"),
    path("collections/", CollectionListView.as_view(), name="collection-list"),
    path("collections/<slug:slug>/", CollectionDetailView.as_view(), name="collection-detail"),
    path("promotions/", PromotionListView.as_view(), name="promotion-list"),
    path("promotions/<slug:slug>/", PromotionDetailView.as_view(), name="promotion-detail"),
    path("lookbooks/", LookbookListView.as_view(), name="lookbook-list"),
    path("lookbooks/<slug:slug>/", LookbookDetailView.as_view(), name="lookbook-detail"),
    path("notices/", NoticeListView.as_view(), name="notice-list"),
    path("faqs/", FAQListView.as_view(), name="faq-list"),
    path("policies/<str:policy_type>/", PolicyPageDetailView.as_view(), name="policy-detail"),
]
