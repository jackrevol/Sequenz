from django.views.generic import TemplateView


class StorefrontView(TemplateView):
    template_name = "storefront/index.html"
