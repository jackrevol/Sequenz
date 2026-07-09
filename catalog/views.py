from django.utils import timezone
from rest_framework import generics

from .models import ProductListing
from .serializers import ProductListingSerializer


class ProductListingListView(generics.ListAPIView):
    serializer_class = ProductListingSerializer

    def get_queryset(self):
        now = timezone.now()
        return (
            ProductListing.objects.select_related("product")
            .prefetch_related("variants__variant")
            .filter(status=ProductListing.Status.ACTIVE)
            .filter(models_visible_at(now))
            .order_by("sort_order", "-created_at")
        )


class ProductListingDetailView(generics.RetrieveAPIView):
    serializer_class = ProductListingSerializer

    def get_queryset(self):
        now = timezone.now()
        return (
            ProductListing.objects.select_related("product")
            .prefetch_related("variants__variant")
            .filter(status=ProductListing.Status.ACTIVE)
            .filter(models_visible_at(now))
        )


def models_visible_at(now):
    from django.db.models import Q

    return (Q(starts_at__isnull=True) | Q(starts_at__lte=now)) & (
        Q(ends_at__isnull=True) | Q(ends_at__gte=now)
    )
