from django.db.models import Q
from django.utils import timezone
from rest_framework import generics

from .models import EditorialCollection, FAQ, HomeBanner, Lookbook, Notice, PolicyPage, Promotion
from .serializers import EditorialCollectionSerializer, FAQSerializer, HomeBannerSerializer, LookbookSerializer, NoticeSerializer, PolicyPageSerializer, PromotionSerializer


def visible_now(now=None):
    now = now or timezone.now()
    return Q(is_visible=True) & (Q(starts_at__isnull=True) | Q(starts_at__lte=now)) & (
        Q(ends_at__isnull=True) | Q(ends_at__gte=now)
    )


class HomeBannerListView(generics.ListAPIView):
    serializer_class = HomeBannerSerializer
    pagination_class = None

    def get_queryset(self):
        return HomeBanner.objects.filter(visible_now()).order_by("sort_order", "-created_at")


class CollectionListView(generics.ListAPIView):
    serializer_class = EditorialCollectionSerializer
    pagination_class = None

    def get_queryset(self):
        return EditorialCollection.objects.filter(visible_now()).prefetch_related(
            "collection_listings__listing__product__brand",
            "collection_listings__listing__product__category",
            "collection_listings__listing__variants__variant",
        )


class CollectionDetailView(generics.RetrieveAPIView):
    serializer_class = EditorialCollectionSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return CollectionListView().get_queryset()


class CuratedContentMixin:
    lookup_field = "slug"

    def get_queryset(self):
        return self.model.objects.filter(visible_now()).prefetch_related(
            self.listing_relation + "__listing__product__brand",
            self.listing_relation + "__listing__product__category",
            self.listing_relation + "__listing__variants__variant",
            self.listing_relation + "__listing__product__images",
        )


class PromotionListView(CuratedContentMixin, generics.ListAPIView):
    model = Promotion
    serializer_class = PromotionSerializer
    pagination_class = None
    listing_relation = "promotion_listings"


class PromotionDetailView(CuratedContentMixin, generics.RetrieveAPIView):
    model = Promotion
    serializer_class = PromotionSerializer
    listing_relation = "promotion_listings"


class LookbookListView(CuratedContentMixin, generics.ListAPIView):
    model = Lookbook
    serializer_class = LookbookSerializer
    pagination_class = None
    listing_relation = "lookbook_listings"

    def get_queryset(self):
        return super().get_queryset().select_related("brand").prefetch_related("images")


class LookbookDetailView(CuratedContentMixin, generics.RetrieveAPIView):
    model = Lookbook
    serializer_class = LookbookSerializer
    listing_relation = "lookbook_listings"

    def get_queryset(self):
        return super().get_queryset().select_related("brand").prefetch_related("images")


class NoticeListView(generics.ListAPIView):
    serializer_class = NoticeSerializer
    pagination_class = None

    def get_queryset(self):
        return Notice.objects.filter(is_visible=True).filter(
            Q(published_at__isnull=True) | Q(published_at__lte=timezone.now())
        )


class FAQListView(generics.ListAPIView):
    serializer_class = FAQSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = FAQ.objects.filter(is_visible=True)
        category = self.request.query_params.get("category")
        return queryset.filter(category=category) if category else queryset


class PolicyPageDetailView(generics.RetrieveAPIView):
    serializer_class = PolicyPageSerializer
    lookup_field = "policy_type"
    queryset = PolicyPage.objects.filter(is_visible=True)
