"""Review model (Prompt 15).

A review is tied to a *specific completed order item*, which is what enforces
the completed-purchase restriction at the database level: one review per
completed line, written by the buyer of that line, on the product they bought.

Rating aggregation is computed server-side (annotated querysets in the catalog
serializers/views), never by the client.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from catalog.models import Product
from orders.models import OrderItem


class Review(models.Model):
    """A buyer's rating + comment for a product after a completed purchase."""

    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
        db_index=True,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="reviews",
        db_index=True,
    )
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Whole-number rating from 1 (worst) to 5 (best).",
    )
    comment = models.TextField(blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order_item"],
                name="reviews_unique_order_item",
            ),
            models.CheckConstraint(
                condition=models.Q(rating__gte=1) & models.Q(rating__lte=5),
                name="reviews_rating_range",
            ),
        ]
        indexes = [
            models.Index(fields=["product"], name="reviews_product_idx"),
            models.Index(fields=["buyer"], name="reviews_buyer_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.rating}/5 on {self.product_id} by buyer {self.buyer_id}"
