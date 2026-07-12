from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/catalog/", include("catalog.urls")),
    path("api/commerce/", include("commerce.urls")),
    path("api/accounts/", include("accounts.urls")),
    path("api/content/", include("content.urls")),
    path("api/community/", include("community.urls")),
    path("", include("storefront.urls")),
]
