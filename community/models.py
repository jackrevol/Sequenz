from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ProductReview(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_reviews")
    order_item = models.OneToOneField("commerce.OrderItem", on_delete=models.PROTECT, related_name="review")
    listing = models.ForeignKey("catalog.ProductListing", on_delete=models.PROTECT, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=160, blank=True)
    body = models.TextField()
    image_urls = models.JSONField(default=list, blank=True)
    is_visible = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class ProductReviewImage(models.Model):
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="reviews/%Y/%m/")
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]


class CustomerInquiry(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ANSWERED = "answered", "Answered"
        CLOSED = "closed", "Closed"

    class Category(models.TextChoices):
        ORDER = "order", "Order"
        DELIVERY = "delivery", "Delivery"
        PRODUCT = "product", "Product"
        RETURN = "return", "Return/Exchange"
        OTHER = "other", "Other"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="inquiries")
    order = models.ForeignKey("commerce.Order", null=True, blank=True, on_delete=models.PROTECT, related_name="inquiries")
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    answer = models.TextField(blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
