import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from catalog.models import Product
from core.models import TimeStampedModel


class Order(TimeStampedModel):
    """A buyer's order (payment envelope) containing items from one or more sellers.

    ``Order.status`` is the *payment-level / envelope* state; individual
    ``OrderItem.item_status`` values track each seller's fulfillment flow
    independently (multi-seller order decision — see docs/ARCHITECTURE.md).
    Transitions are driven exclusively by ``orders.state_machine`` and applied
    through ``orders.services``; no view ever writes ``status`` directly.
    """

    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Pending payment"
        PAID = "paid", "Paid"
        CONFIRMED = "confirmed", "Confirmed"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        PAYMENT_FAILED = "payment_failed", "Payment failed"
        REFUNDED = "refunded", "Refunded"

    class PaymentMethod(models.TextChoices):
        CARD = "card", "Card"
        PAYPAL = "paypal", "PayPal"
        CASH_ON_DELIVERY = "cod", "Cash on Delivery"

    order_number = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
        default="",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
        db_index=True,
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CARD,
    )
    shipping_address = models.JSONField(default=dict, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    placed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ["-placed_at"]

    def __str__(self) -> str:
        return f"Order {self.order_number}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = uuid.uuid4().hex[:16].upper()
        super().save(*args, **kwargs)


class OrderItem(TimeStampedModel):
    """A single product line within an order, owned by one seller.

    ``item_status`` mirrors the fulfillment subset of the order states
    (PENDING/CONFIRMED/SHIPPED/DELIVERED/COMPLETED/CANCELLED) so each seller
    manages their own items independently. ``seller`` is snapshotted at order
    time from the product's seller.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sold_items",
        db_index=True,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    product_name = models.CharField(max_length=255)
    product_sku = models.CharField(max_length=64, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    attributes = models.JSONField(default=dict, blank=True)
    item_status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    class Meta:
        verbose_name = "Order item"
        verbose_name_plural = "Order items"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.product_name}"

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity
