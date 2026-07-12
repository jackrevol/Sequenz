from django.contrib import admin

from .models import CollectionListing, EditorialCollection, FAQ, HomeBanner, Lookbook, LookbookImage, LookbookListing, Notice, PolicyPage, Promotion, PromotionListing


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


class PromotionListingInline(admin.TabularInline):
    model = PromotionListing
    extra = 0
    autocomplete_fields = ("listing",)


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_visible", "sort_order", "starts_at", "ends_at")
    list_editable = ("is_visible", "sort_order")
    prepopulated_fields = {"slug": ("title",)}
    inlines = (PromotionListingInline,)


class LookbookImageInline(admin.TabularInline):
    model = LookbookImage
    extra = 0


class LookbookListingInline(admin.TabularInline):
    model = LookbookListing
    extra = 0
    autocomplete_fields = ("listing",)


@admin.register(Lookbook)
class LookbookAdmin(admin.ModelAdmin):
    list_display = ("title", "brand", "season_label", "is_visible", "sort_order")
    list_editable = ("is_visible", "sort_order")
    prepopulated_fields = {"slug": ("title",)}
    inlines = (LookbookImageInline, LookbookListingInline)


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ("title", "is_pinned", "is_visible", "published_at")
    list_filter = ("is_pinned", "is_visible")
    search_fields = ("title", "content")


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "category", "is_visible", "sort_order")
    list_filter = ("category", "is_visible")
    list_editable = ("is_visible", "sort_order")
    search_fields = ("question", "answer")


@admin.register(PolicyPage)
class PolicyPageAdmin(admin.ModelAdmin):
    list_display = ("title", "policy_type", "version", "is_visible", "effective_at")
    list_filter = ("policy_type", "is_visible")
