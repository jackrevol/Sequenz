from django.db import transaction
from rest_framework import serializers

from commerce.models import Order, OrderItem

from .models import CustomerInquiry, ProductReview


class ProductReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.SerializerMethodField()
    image_urls = serializers.SerializerMethodField()

    def get_reviewer_name(self, review):
        profile = getattr(review.user, "member_profile", None)
        name = profile.name if profile else review.user.username
        return name[:1] + "*" * max(len(name) - 1, 1)

    def get_image_urls(self, review):
        urls = list(review.image_urls or [])
        request = self.context.get("request")
        for image in review.images.all():
            url = image.image.url
            urls.append(request.build_absolute_uri(url) if request else url)
        return urls

    class Meta:
        model = ProductReview
        fields = ["id", "listing_id", "rating", "title", "body", "image_urls", "reviewer_name", "created_at"]
        read_only_fields = ["listing_id", "reviewer_name", "created_at"]


class ProductReviewCreateSerializer(serializers.Serializer):
    order_item_id = serializers.IntegerField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    title = serializers.CharField(max_length=160, required=False, allow_blank=True)
    body = serializers.CharField()
    image_urls = serializers.ListField(child=serializers.URLField(), required=False, max_length=5)

    def validate_order_item_id(self, value):
        user = self.context["request"].user
        try:
            item = OrderItem.objects.select_related("order", "listing").get(pk=value, order__user=user)
        except OrderItem.DoesNotExist as exc:
            raise serializers.ValidationError("구매한 주문상품을 찾을 수 없습니다.") from exc
        if item.order.fulfillment_status != Order.FulfillmentStatus.DELIVERED:
            raise serializers.ValidationError("배송이 완료된 주문상품만 후기를 작성할 수 있습니다.")
        if item.listing_id is None:
            raise serializers.ValidationError("판매 종료된 상품에는 후기를 작성할 수 없습니다.")
        if ProductReview.objects.filter(order_item=item).exists():
            raise serializers.ValidationError("이미 후기를 작성한 주문상품입니다.")
        self.context["order_item"] = item
        return value

    @transaction.atomic
    def create(self, validated_data):
        item = self.context["order_item"]
        review = ProductReview.objects.create(
            user=self.context["request"].user,
            order_item=item,
            listing=item.listing,
            rating=validated_data["rating"],
            title=validated_data.get("title", ""),
            body=validated_data["body"],
            image_urls=validated_data.get("image_urls", []),
        )
        item.review_status = "written"
        item.save(update_fields=["review_status"])
        return review


class CustomerInquirySerializer(serializers.ModelSerializer):
    order_id = serializers.PrimaryKeyRelatedField(
        source="order", queryset=Order.objects.all(), allow_null=True, required=False
    )
    class Meta:
        model = CustomerInquiry
        fields = ["id", "order_id", "category", "subject", "body", "status", "answer", "answered_at", "created_at"]
        read_only_fields = ["status", "answer", "answered_at", "created_at"]

    def validate_order_id(self, value):
        if value and value.user_id != self.context["request"].user.id:
            raise serializers.ValidationError("본인의 주문만 문의에 연결할 수 있습니다.")
        return value
