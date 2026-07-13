from django.views.generic import TemplateView
from django.views.generic.detail import DetailView

from catalog.models import ProductListing


class StorefrontView(TemplateView):
    template_name = "storefront/index.html"


class StorefrontPageView(TemplateView):
    template_name = "storefront/page.html"


class ProductDetailPageView(DetailView):
    model = ProductListing
    template_name = "storefront/product_detail.html"
    context_object_name = "listing"

    def get_queryset(self):
        return ProductListing.objects.filter(status=ProductListing.Status.ACTIVE)
