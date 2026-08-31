"""Catalog models: Category, Product, ProductImage, Favorite.

No APIs here — serializers/views arrive in Prompt 04.
"""

import os
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .validators import IMAGE_VALIDATORS


def product_image_upload_to(instance, filename):
    """Store images under ``MEDIA_ROOT/products/<product_id>/``."""
    product_id = instance.product_id or "unsaved"
    ext = os.path.splitext(filename)[1].lower()
    return f"products/{product_id}/{uuid4().hex}{ext}"


class Category(models.Model):
    """Product category, optionally nested under a parent."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    """A reusable item listed by a seller."""

    class Condition(models.TextChoices):
        NEW = "NEW", "New"
        LIKE_NEW = "LIKE_NEW", "Like new"
        GOOD = "GOOD", "Good"
        FAIR = "FAIR", "Fair"
        USED = "USED", "Used"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        SOLD = "SOLD", "Sold"
        INACTIVE = "INACTIVE", "Inactive"

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="products",
        db_index=True,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="products",
        null=True,
        blank=True,
        db_index=True,
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    condition = models.CharField(max_length=20, choices=Condition.choices)
    # Plain IntegerField so the explicit CheckConstraint below is the single
    # source of truth for the quantity >= 0 rule.
    quantity = models.IntegerField(default=1)
    location = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gt=0),
                name="catalog_product_price_gt_0",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="catalog_product_quantity_gte_0",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.price is not None and self.price <= 0:
            raise ValidationError({"price": "Price must be greater than zero."})
        if self.quantity is not None and self.quantity < 0:
            raise ValidationError({"quantity": "Quantity cannot be negative."})

    def effective_price(self):
        return self.price


class ProductImage(models.Model):
    """An image attached to a product."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(
        upload_to=product_image_upload_to,
        validators=IMAGE_VALIDATORS,
    )
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Image #{self.pk} for {self.product_id}"

    def save(self, *args, **kwargs):
        # Enforce image validators even on direct ORM saves.
        self.full_clean(validate_unique=False)
        super().save(*args, **kwargs)


class Favorite(models.Model):
    """A user's saved/favorited product."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="favorited_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="catalog_favorite_unique_user_product",
            ),
        ]

    def __str__(self):
        return f"{self.user_id} -> {self.product_id}"
