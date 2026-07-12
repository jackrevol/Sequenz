from django.db.models import Q
from django.utils import timezone
from rest_framework import generics

from .models import EditorialCollection, HomeBanner
from .serializers import EditorialCollectionSerializer, HomeBannerSerializer


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
