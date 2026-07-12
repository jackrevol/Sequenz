from django.contrib import admin

from .models import CollectionListing, EditorialCollection, HomeBanner


@admin.register(HomeBanner)
class HomeBannerAdmin(admin.ModelAdmin):
    list_display = ("title", "media_type", "link_type", "is_visible", "sort_order", "starts_at", "ends_at")
    list_filter = ("media_type", "link_type", "is_visible")
    list_editable = ("is_visible", "sort_order")
    search_fields = ("title", "subtitle")


class CollectionListingInline(admin.TabularInline):
    model = CollectionListing
    extra = 0
    autocomplete_fields = ("listing",)


@admin.register(EditorialCollection)
class EditorialCollectionAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_visible", "sort_order", "starts_at", "ends_at")
    list_editable = ("is_visible", "sort_order")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "summary")
    inlines = (CollectionListingInline,)
