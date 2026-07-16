from django.db import models


class HomeBanner(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "image", "이미지"
        VIDEO = "video", "동영상"

    class LinkType(models.TextChoices):
        NONE = "none", "연결 없음"
        LISTING = "listing", "판매 상품"
        BRAND = "brand", "브랜드"
        COLLECTION = "collection", "컬렉션"
        EXTERNAL = "external", "외부 URL"

    title = models.CharField(max_length=160)
    subtitle = models.CharField(max_length=300, blank=True)
    media_type = models.CharField(max_length=10, choices=MediaType.choices, default=MediaType.IMAGE)
    media_url = models.URLField()
    mobile_media_url = models.URLField(blank=True)
    poster_url = models.URLField(blank=True)
    link_type = models.CharField(max_length=20, choices=LinkType.choices, default=LinkType.NONE)
    link_url = models.CharField(max_length=500, blank=True)
    button_label = models.CharField(max_length=80, blank=True)
    is_visible = models.BooleanField(default=True, db_index=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]

    def __str__(self):
        return self.title


class EditorialCollection(models.Model):
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    summary = models.TextField(blank=True)
    hero_image_url = models.URLField(blank=True)
    is_visible = models.BooleanField(default=True, db_index=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    listings = models.ManyToManyField("catalog.ProductListing", through="CollectionListing", related_name="collections")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]

    def __str__(self):
        return self.title


class CollectionListing(models.Model):
    collection = models.ForeignKey(EditorialCollection, on_delete=models.CASCADE, related_name="collection_listings")
    listing = models.ForeignKey("catalog.ProductListing", on_delete=models.CASCADE, related_name="collection_links")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["collection", "listing"], name="unique_collection_listing")
        ]


class Promotion(models.Model):
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    summary = models.TextField(blank=True)
    hero_image_url = models.URLField(blank=True)
    body_html = models.TextField(blank=True)
    is_visible = models.BooleanField(default=True, db_index=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    listings = models.ManyToManyField("catalog.ProductListing", through="PromotionListing", related_name="promotions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]


class PromotionListing(models.Model):
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name="promotion_listings")
    listing = models.ForeignKey("catalog.ProductListing", on_delete=models.CASCADE)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [models.UniqueConstraint(fields=["promotion", "listing"], name="unique_promotion_listing")]


class Lookbook(models.Model):
    brand = models.ForeignKey("catalog.Brand", null=True, blank=True, on_delete=models.SET_NULL, related_name="lookbooks")
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    season_label = models.CharField(max_length=80, blank=True)
    summary = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    cover_image_url = models.URLField(blank=True)
    is_visible = models.BooleanField(default=True, db_index=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    listings = models.ManyToManyField("catalog.ProductListing", through="LookbookListing", related_name="lookbooks")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]


class LookbookImage(models.Model):
    lookbook = models.ForeignKey(Lookbook, on_delete=models.CASCADE, related_name="images")
    image_url = models.URLField()
    caption = models.CharField(max_length=240, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]


class LookbookListing(models.Model):
    lookbook = models.ForeignKey(Lookbook, on_delete=models.CASCADE, related_name="lookbook_listings")
    listing = models.ForeignKey("catalog.ProductListing", on_delete=models.CASCADE)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [models.UniqueConstraint(fields=["lookbook", "listing"], name="unique_lookbook_listing")]


class Notice(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_pinned = models.BooleanField(default=False, db_index=True)
    is_visible = models.BooleanField(default=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-published_at", "-created_at"]


class FAQ(models.Model):
    category = models.CharField(max_length=80, db_index=True)
    question = models.CharField(max_length=240)
    answer = models.TextField()
    sort_order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["category", "sort_order", "id"]


class PolicyPage(models.Model):
    class PolicyType(models.TextChoices):
        TERMS = "terms", "이용약관"
        PRIVACY = "privacy", "개인정보처리방침"
        SHIPPING = "shipping", "배송 정책"
        RETURNS = "returns", "교환·반품 정책"

    policy_type = models.CharField(max_length=30, choices=PolicyType.choices, unique=True)
    title = models.CharField(max_length=160)
    content = models.TextField()
    version = models.CharField(max_length=40)
    is_visible = models.BooleanField(default=True)
    effective_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
