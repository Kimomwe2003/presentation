"""Payment model (Prompt 09 — ClickPesa integration).

A ``Payment`` is one payment attempt against an order. An order may have many
attempts (retry flow); at most one is ``PENDING`` at a time. ``Order.status`` is
only ever moved to ``PAID`` by verified payment events (webhook / manual verify
against ClickPesa) — never by a raw client claim.
"""

from decimal import Decimal

from django.db import models

from core.models import TimeStampedModel
from orders.models import Order


class Payment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESSFUL = "successful", "Successful"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    class Provider(models.TextChoices):
        CLICKPESA = "clickpesa", "ClickPesa"

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="payments",
        db_index=True,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    external_reference = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        default="",
        help_text="The alphanumeric orderReference sent to ClickPesa (unique per attempt).",
    )
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.CLICKPESA,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    # ClickPesa's transaction id (data.id) — stored so a later webhook or the
    # reconciliation job can correlate an inbound callback even when it arrives
    # without our orderReference (matched by id).
    clickpesa_transaction_id = models.CharField(
        max_length=64, blank=True, default="", db_index=True
    )
    failure_reason = models.CharField(max_length=255, blank=True, default="")
    network_channel = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="Mobile money channel detected by ClickPesa (e.g. M-PESA, TIGO-PESA).",
    )
    raw_provider_response = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Payment {self.external_reference} ({self.get_status_display()})"
