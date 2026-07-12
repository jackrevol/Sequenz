from django.urls import path

from .views import InquiryDetailView, InquiryListCreateView, ListingReviewListView, ProductReviewCreateView, ReviewableOrderItemListView


urlpatterns = [
    path("reviews/", ProductReviewCreateView.as_view(), name="review-create"),
    path("reviews/listing/<int:listing_id>/", ListingReviewListView.as_view(), name="listing-reviews"),
    path("reviews/reviewable/", ReviewableOrderItemListView.as_view(), name="reviewable-order-items"),
    path("inquiries/", InquiryListCreateView.as_view(), name="inquiry-list-create"),
    path("inquiries/<int:pk>/", InquiryDetailView.as_view(), name="inquiry-detail"),
]
