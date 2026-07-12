from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/catalog/", include("catalog.urls")),
    path("api/commerce/", include("commerce.urls")),
    path("api/accounts/", include("accounts.urls")),
    path("api/content/", include("content.urls")),
    path("api/community/", include("community.urls")),
    path("api/benefits/", include("benefits.urls")),
    path("operations/", include("integrations.urls")),
    path("", include("storefront.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
