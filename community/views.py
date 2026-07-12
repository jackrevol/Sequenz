from django.db.models import Avg, Count
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CustomerInquiry, ProductReview
from .serializers import CustomerInquirySerializer, ProductReviewCreateSerializer, ProductReviewSerializer


class ListingReviewListView(APIView):
    def get(self, request, listing_id):
        reviews = ProductReview.objects.filter(listing_id=listing_id, is_visible=True).select_related(
            "user", "user__member_profile"
        )
        summary = reviews.aggregate(count=Count("id"), average_rating=Avg("rating"))
        return Response({
            "summary": {"count": summary["count"], "average_rating": round(summary["average_rating"] or 0, 1)},
            "results": ProductReviewSerializer(reviews[:50], many=True).data,
        })


class ProductReviewCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ProductReviewCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        return Response(ProductReviewSerializer(review).data, status=status.HTTP_201_CREATED)


class InquiryListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CustomerInquirySerializer

    def get_queryset(self):
        return CustomerInquiry.objects.filter(user=self.request.user).select_related("order")

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "request": self.request}

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class InquiryDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CustomerInquirySerializer

    def get_queryset(self):
        return CustomerInquiry.objects.filter(user=self.request.user).select_related("order")
