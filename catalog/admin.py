import re

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from .models import Brand, Category, Product, ProductAttribute, ProductImage, ProductInformationNotice, ProductListing, ProductListingVariant, ProductSyncSnapshot, ProductVariant, SearchKeyword
from integrations.models import ExternalApiLog, IntegrationJob, OperationsAuditLog
from integrations.sabangnet_products import SabangnetProductClient, sync_product_safely


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_visible", "sort_order", "updated_at")
    list_editable = ("is_visible", "sort_order")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "level", "is_visible", "sort_order")
    list_filter = ("level", "is_visible")
    list_editable = ("is_visible", "sort_order")
    search_fields = ("name", "slug", "sabangnet_code")


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ("option_display_name", "variant_code", "barcode", "stock_quantity", "reserved_quantity", "safety_stock_quantity", "supply_status")
    readonly_fields = ("variant_code", "barcode", "reserved_quantity")


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ("source", "image_url", "alt_text", "sort_order", "is_primary", "sabangnet_image_srno")
    readonly_fields = ("sabangnet_image_srno",)


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 0


class ProductInformationNoticeInline(admin.StackedInline):
    model = ProductInformationNotice
    extra = 0
    max_num = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    change_list_template = "admin/catalog/product/change_list.html"
    list_display = ("name", "custom_product_code", "brand", "category", "selling_price", "supply_status", "synced_at")
    list_filter = ("brand", "category", "supply_status")
    search_fields = ("name", "custom_product_code", "sabangnet_product_code", "product_tags")
    readonly_fields = ("sabangnet_product_code", "raw_sabangnet_payload", "synced_at")
    inlines = (ProductVariantInline, ProductImageInline, ProductAttributeInline, ProductInformationNoticeInline)

    def get_urls(self):
        custom_urls = [
            path(
                "sabangnet-sync/",
                self.admin_site.admin_view(self.sabangnet_sync_view),
                name="catalog_product_sabangnet_sync",
            ),
        ]
        return custom_urls + super().get_urls()

    def sabangnet_sync_view(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied

        if request.method == "POST":
            identifier_type = request.POST.get("identifier_type", "product_code")
            mode = request.POST.get("mode", "codes")
            codes = self._sync_codes(request.POST.get("codes", ""), identifier_type, mode)
            if not codes:
                self.message_user(request, "동기화할 상품코드가 없습니다.", level=messages.ERROR)
            elif len(codes) > 100:
                self.message_user(
                    request,
                    f"한 번에 최대 100개까지 동기화할 수 있습니다. 현재 대상은 {len(codes)}개입니다.",
                    level=messages.ERROR,
                )
            else:
                result = self._run_sabangnet_sync(request, codes, identifier_type)
                if result["failure_count"]:
                    level = messages.WARNING if result["success_count"] else messages.ERROR
                    message = (
                        f"사방넷 상품 동기화 완료: 성공 {result['success_count']}건, "
                        f"실패 {result['failure_count']}건. 실패 사유는 외부 연동 로그에서 확인하세요."
                    )
                else:
                    level = messages.SUCCESS
                    message = f"사방넷 상품 {result['success_count']}건을 성공적으로 가져왔습니다."
                self.message_user(request, message, level=level)
                return redirect(reverse("admin:catalog_product_changelist"))

        context = {
            **self.admin_site.each_context(request),
            "title": "사방넷 상품 가져오기",
            "opts": self.model._meta,
            "has_view_permission": self.has_view_permission(request),
            "configured": {
                "base_url": bool(settings.SABANGNET_API_BASE_URL),
                "service_account": bool(settings.SABANGNET_SVC_ACCOUNT_ID),
                "authentication": bool(
                    settings.SABANGNET_BEARER_TOKEN
                    or (settings.SABANGNET_CLIENT_ID and settings.SABANGNET_CLIENT_SECRET)
                ),
            },
            "existing_count": Product.objects.exclude(sabangnet_product_code="").count(),
        }
        return TemplateResponse(request, "admin/catalog/product/sabangnet_sync.html", context)

    @staticmethod
    def _sync_codes(raw_codes, identifier_type, mode):
        if mode == "existing":
            field = "custom_product_code" if identifier_type == "custom_product_code" else "sabangnet_product_code"
            return list(Product.objects.exclude(**{f"{field}__isnull": True}).exclude(**{field: ""}).values_list(field, flat=True))
        return list(dict.fromkeys(code.strip() for code in re.split(r"[\s,]+", raw_codes) if code.strip()))

    @staticmethod
    def _run_sabangnet_sync(request, codes, identifier_type):
        job = IntegrationJob.objects.create(
            provider="sabangnet",
            job_type="manual_product_sync",
            status=IntegrationJob.Status.RUNNING,
            started_at=timezone.now(),
            total_count=len(codes),
            requested_by=request.user,
        )
        client = SabangnetProductClient()
        success_count = 0
        errors = []
        for code in codes:
            try:
                kwargs = {identifier_type: code}
                payload = client.fetch_product(**kwargs)
                sync_product_safely(payload)
                success_count += 1
            except Exception as exc:
                safe_error = str(exc)[:500]
                errors.append(f"{code}: {safe_error}")
                ExternalApiLog.objects.create(
                    provider="sabangnet",
                    job=job,
                    operation="manual_product_sync",
                    request_summary={"identifier_type": identifier_type, "product_identifier": code},
                    error_code=getattr(exc, "code", "SYNC_FAILED") or "SYNC_FAILED",
                    error_message=safe_error,
                )
        failure_count = len(codes) - success_count
        job.success_count = success_count
        job.failure_count = failure_count
        job.status = (
            IntegrationJob.Status.SUCCEEDED if failure_count == 0
            else IntegrationJob.Status.FAILED if success_count == 0
            else IntegrationJob.Status.PARTIAL
        )
        job.error_summary = "\n".join(errors)[:2000]
        job.finished_at = timezone.now()
        job.save(update_fields=["success_count", "failure_count", "status", "error_summary", "finished_at"])
        OperationsAuditLog.objects.create(
            actor=request.user,
            action="sabangnet_product_manual_sync",
            target_type="Product",
            target_id="bulk",
            before_summary={"requested_count": len(codes), "identifier_type": identifier_type},
            after_summary={"success_count": success_count, "failure_count": failure_count, "job_id": job.pk},
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return {"success_count": success_count, "failure_count": failure_count, "job": job}


class ProductListingVariantInline(admin.TabularInline):
    model = ProductListingVariant
    extra = 0
    autocomplete_fields = ("variant",)


@admin.register(ProductListing)
class ProductListingAdmin(admin.ModelAdmin):
    list_display = ("display_name", "listing_code", "status", "selling_price_snapshot", "is_featured", "sort_order", "updated_at")
    list_filter = ("status", "is_featured", "is_new_label", "is_sale_label", "sales_channel")
    list_editable = ("status", "is_featured", "sort_order")
    search_fields = ("display_name", "listing_code", "slug", "search_keywords")
    prepopulated_fields = {"slug": ("display_name",)}
    autocomplete_fields = ("product",)
    inlines = (ProductListingVariantInline,)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("product", "option_display_name", "variant_code", "stock_quantity", "reserved_quantity", "safety_stock_quantity", "supply_status")
    list_filter = ("supply_status",)
    search_fields = ("product__name", "variant_code", "barcode", "option_display_name")


@admin.register(ProductSyncSnapshot)
class ProductSyncSnapshotAdmin(admin.ModelAdmin):
    list_display = ("sabangnet_product_code", "product", "status", "synced_at")
    list_filter = ("status", "synced_at")
    search_fields = ("sabangnet_product_code", "product__name", "error_message")
    readonly_fields = tuple(field.name for field in ProductSyncSnapshot._meta.fields)


@admin.register(SearchKeyword)
class SearchKeywordAdmin(admin.ModelAdmin):
    list_display = ("keyword", "search_count", "is_recommended", "is_visible", "sort_order", "last_searched_at")
    list_editable = ("is_recommended", "is_visible", "sort_order")
    search_fields = ("keyword",)
