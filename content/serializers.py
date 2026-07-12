from rest_framework import serializers
from django.utils import timezone

from catalog.serializers import ProductListingSerializer

from .models import EditorialCollection, FAQ, HomeBanner, Lookbook, Notice, PolicyPage, Promotion


class HomeBannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomeBanner
        fields = [
            "id", "title", "subtitle", "media_type", "media_url", "mobile_media_url",
            "poster_url", "link_type", "link_url", "button_label",
        ]


class EditorialCollectionSerializer(serializers.ModelSerializer):
    listings = serializers.SerializerMethodField()

    def get_listings(self, collection):
        now = timezone.now()
        ordered = [
            link.listing for link in collection.collection_listings.all()
            if link.listing.status == "active"
            and (link.listing.starts_at is None or link.listing.starts_at <= now)
            and (link.listing.ends_at is None or link.listing.ends_at >= now)
            and (link.listing.product.brand is None or link.listing.product.brand.is_visible)
            and (link.listing.product.category is None or link.listing.product.category.is_visible)
        ]
        return ProductListingSerializer(ordered, many=True).data

    class Meta:
        model = EditorialCollection
        fields = ["id", "title", "slug", "summary", "hero_image_url", "listings"]


class CuratedContentSerializer(serializers.ModelSerializer):
    listings = serializers.SerializerMethodField()

    def get_listings(self, instance):
        relation = instance.promotion_listings if isinstance(instance, Promotion) else instance.lookbook_listings
        return ProductListingSerializer([link.listing for link in relation.all()], many=True).data


class PromotionSerializer(CuratedContentSerializer):
    class Meta:
        model = Promotion
        fields = ["id", "title", "slug", "summary", "hero_image_url", "body_html", "listings"]


class LookbookSerializer(CuratedContentSerializer):
    brand_name = serializers.CharField(source="brand.name", default="")
    images = serializers.SerializerMethodField()

    def get_images(self, instance):
        return [{"image_url": image.image_url, "caption": image.caption} for image in instance.images.all()]

    class Meta:
        model = Lookbook
        fields = ["id", "brand_name", "title", "slug", "season_label", "summary", "body_html", "cover_image_url", "images", "listings"]


class NoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notice
        fields = ["id", "title", "content", "is_pinned", "published_at"]


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ["id", "category", "question", "answer"]


class PolicyPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyPage
        fields = ["policy_type", "title", "content", "version", "effective_at"]
