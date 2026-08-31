from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel

from .managers import CartItemManager, CartManager


class Cart(TimeStampedModel):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
        null=True,
        blank=True,
    )
    session_key = models.CharField(
        max_length=40,
        unique=True,
        null=True,
        blank=True,
        help_text="Identifier for anonymously-created carts.",
    )
    expires_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
        help_text="Anonymously created carts are deleted after this timestamp.",
    )

    objects = CartManager()

    class Meta:
        verbose_name = "Cart"
        verbose_name_plural = "Carts"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(owner__isnull=False, session_key__isnull=True)
                | models.Q(owner__isnull=True, session_key__isnull=False),
                name="cart_owner_or_session_key",
            )
        ]

    def __str__(self) -> str:
        label = self.owner or f"session:{self.session_key}"
        return f"Cart #{self.pk} ({label})"

    @property
    def is_anonymous(self) -> bool:
        return self.owner is None

    @property
    def subtotal(self) -> Decimal:
        return sum((item.line_total for item in self.items.all()), Decimal("0.00"))

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items.all())

    def flush(self) -> None:
        self.items.all().delete()


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    attributes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Selected variant attributes (e.g. size, colour).",
    )

    objects = CartItemManager()

    class Meta:
        verbose_name = "Cart item"
        verbose_name_plural = "Cart items"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"],
                condition=models.Q(attributes={}),
                name="unique_cart_product_no_attributes",
            )
        ]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.product} in cart #{self.cart_id}"

    @property
    def line_total(self) -> Decimal:
        return self.product.effective_price() * self.quantity

    @property
    def price(self) -> Decimal:
        return self.product.effective_price()

    @property
    def total(self) -> Decimal:
        return self.line_total
