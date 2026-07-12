from django.db.models import Avg, Count
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from commerce.models import Order, OrderItem

from .models import CustomerInquiry, ProductReview, ProductReviewImage
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
        files = request.FILES.getlist("images")
        if len(files) > 5:
            return Response({"detail": "후기 이미지는 최대 5장까지 등록할 수 있습니다."}, status=status.HTTP_400_BAD_REQUEST)
        for image in files:
            if not image.content_type.startswith("image/") or image.size > 10 * 1024 * 1024:
                return Response({"detail": "10MB 이하 이미지 파일만 등록할 수 있습니다."}, status=status.HTTP_400_BAD_REQUEST)
        review = serializer.save()
        for index, image in enumerate(files):
            ProductReviewImage.objects.create(review=review, image=image, sort_order=index)
        return Response(ProductReviewSerializer(review, context={"request": request}).data, status=status.HTTP_201_CREATED)


class ReviewableOrderItemListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        items = OrderItem.objects.filter(
            order__user=request.user, order__fulfillment_status=Order.FulfillmentStatus.DELIVERED,
            listing__isnull=False,
        ).filter(review__isnull=True).select_related("order", "listing")
        return Response({"results": [
            {
                "order_item_id": item.id, "order_number": item.order.order_number,
                "listing_id": item.listing_id, "product_name": item.product_name_snapshot,
                "option_name": item.option_name_snapshot, "delivered_at": item.order.updated_at,
            }
            for item in items
        ]})


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
