from django.urls import include, path


urlpatterns = [
    path("api/catalog/", include("catalog.urls")),
    path("api/commerce/", include("commerce.urls")),
]
