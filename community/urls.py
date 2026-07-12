from django.urls import path

from .views import InquiryDetailView, InquiryListCreateView, ListingReviewListView, ProductReviewCreateView


urlpatterns = [
    path("reviews/", ProductReviewCreateView.as_view(), name="review-create"),
    path("reviews/listing/<int:listing_id>/", ListingReviewListView.as_view(), name="listing-reviews"),
    path("inquiries/", InquiryListCreateView.as_view(), name="inquiry-list-create"),
    path("inquiries/<int:pk>/", InquiryDetailView.as_view(), name="inquiry-detail"),
]
