from django.utils import timezone
from django.db.models import F, Q
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Brand, Category, ProductAttribute, ProductListing, SearchKeyword
from .serializers import BrandSerializer, CategorySerializer, ProductListingSerializer, SearchKeywordSerializer


class BrandListView(generics.ListAPIView):
    serializer_class = BrandSerializer
    pagination_class = None
    queryset = Brand.objects.filter(is_visible=True).order_by("sort_order", "name")


class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer
    pagination_class = None
    queryset = Category.objects.filter(is_visible=True).select_related("parent").order_by("level", "sort_order", "name")


class ProductListingListView(generics.ListAPIView):
    serializer_class = ProductListingSerializer

    def get_queryset(self):
        now = timezone.now()
        queryset = (
            ProductListing.objects.select_related("product", "product__brand", "product__category")
            .prefetch_related("variants__variant", "product__images", "product__attributes")
            .filter(status=ProductListing.Status.ACTIVE)
            .filter(models_visible_at(now))
            .order_by("sort_order", "-created_at")
        )
        query = self.request.query_params.get("q", "").strip()
        brand = self.request.query_params.get("brand", "").strip()
        category = self.request.query_params.get("category", "").strip()
        featured = self.request.query_params.get("featured", "").lower()
        ordering = self.request.query_params.get("ordering", "newest")
        if query:
            queryset = queryset.filter(
                Q(display_name__icontains=query)
                | Q(search_keywords__icontains=query)
                | Q(product__name__icontains=query)
                | Q(product__custom_product_code__icontains=query)
                | Q(product__brand__name__icontains=query)
                | Q(product__category__name__icontains=query)
            )
            SearchKeyword.objects.update_or_create(
                keyword=query[:120],
                defaults={"last_searched_at": now},
            )
            SearchKeyword.objects.filter(keyword=query[:120]).update(search_count=F("search_count") + 1)
        if brand:
            queryset = queryset.filter(product__brand__slug=brand)
        if category:
            queryset = queryset.filter(product__category__slug=category)
        if featured in {"1", "true", "yes"}:
            queryset = queryset.filter(is_featured=True)
        for raw_filter in self.request.query_params.getlist("attribute"):
            name, separator, value = raw_filter.partition(":")
            if separator and name.strip() and value.strip():
                queryset = queryset.filter(
                    product__attributes__name=name.strip(), product__attributes__value=value.strip(),
                    product__attributes__is_filterable=True,
                )
        orderings = {
            "newest": ("-created_at",),
            "price_asc": ("selling_price_snapshot", "id"),
            "price_desc": ("-selling_price_snapshot", "id"),
            "recommended": ("sort_order", "-created_at"),
        }
        return queryset.order_by(*orderings.get(ordering, orderings["newest"])).distinct()


class ProductListingDetailView(generics.RetrieveAPIView):
    serializer_class = ProductListingSerializer

    def get_queryset(self):
        now = timezone.now()
        return (
            ProductListing.objects.select_related("product", "product__brand", "product__category")
            .prefetch_related("variants__variant", "product__images", "product__attributes")
            .filter(status=ProductListing.Status.ACTIVE)
            .filter(models_visible_at(now))
        )


def models_visible_at(now):
    from django.db.models import Q

    return (Q(starts_at__isnull=True) | Q(starts_at__lte=now)) & (
        Q(ends_at__isnull=True) | Q(ends_at__gte=now)
    )


class ProductFilterView(APIView):
    def get(self, request):
        values = ProductAttribute.objects.filter(
            is_filterable=True, product__listings__status=ProductListing.Status.ACTIVE
        ).values_list("name", "value").distinct().order_by("name", "value")
        grouped = {}
        for name, value in values:
            grouped.setdefault(name, []).append(value)
        return Response([{"name": name, "values": items} for name, items in grouped.items()])


class SearchKeywordView(APIView):
    def get(self, request):
        recommended = SearchKeyword.objects.filter(is_visible=True, is_recommended=True)[:10]
        popular = SearchKeyword.objects.filter(is_visible=True, search_count__gt=0).order_by("-search_count")[:10]
        return Response({
            "recommended": SearchKeywordSerializer(recommended, many=True).data,
            "popular": SearchKeywordSerializer(popular, many=True).data,
        })
