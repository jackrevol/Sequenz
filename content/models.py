from django.db import models


class HomeBanner(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    class LinkType(models.TextChoices):
        NONE = "none", "None"
        LISTING = "listing", "Product listing"
        BRAND = "brand", "Brand"
        COLLECTION = "collection", "Collection"
        EXTERNAL = "external", "External URL"

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
