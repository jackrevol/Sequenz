from django.contrib import admin
from django.utils import timezone

from .models import CustomerInquiry, ProductReview, ProductReviewImage


class ProductReviewImageInline(admin.TabularInline):
    model = ProductReviewImage
    extra = 0


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ("listing", "user", "rating", "is_visible", "created_at")
    list_filter = ("rating", "is_visible", "created_at")
    list_editable = ("is_visible",)
    search_fields = ("listing__display_name", "user__username", "title", "body")
    readonly_fields = ("user", "order_item", "listing", "created_at", "updated_at")
    inlines = (ProductReviewImageInline,)


@admin.register(CustomerInquiry)
class CustomerInquiryAdmin(admin.ModelAdmin):
    list_display = ("subject", "user", "category", "status", "created_at", "answered_at")
    list_filter = ("status", "category", "created_at")
    search_fields = ("subject", "body", "answer", "user__username", "order__order_number")
    readonly_fields = ("user", "order", "category", "subject", "body", "created_at", "updated_at")
    actions = ("mark_answered",)

    @admin.action(description="선택한 문의를 답변완료로 변경")
    def mark_answered(self, request, queryset):
        queryset.exclude(answer="").update(status=CustomerInquiry.Status.ANSWERED, answered_at=timezone.now())

    def save_model(self, request, obj, form, change):
        if obj.answer and obj.status == CustomerInquiry.Status.OPEN:
            obj.status = CustomerInquiry.Status.ANSWERED
            obj.answered_at = timezone.now()
        super().save_model(request, obj, form, change)
