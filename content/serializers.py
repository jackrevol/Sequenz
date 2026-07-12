from rest_framework import serializers
from django.utils import timezone

from catalog.serializers import ProductListingSerializer

from .models import EditorialCollection, HomeBanner


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
