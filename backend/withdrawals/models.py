"""Withdrawal request model (Prompt 12).

A withdrawal request records a user's decision to move wallet earnings to a
mobile-money number. The money movement itself lives in the wallet ledger (see
:mod:`wallet.services`): a WITHDRAWAL ledger row is written the moment the
request is created (holding the funds), and a REFUND ledger row reverses it
atomically if the request is later failed or rejected.

The request is a separate record because it has its own lifecycle — requested
by the user, then processed/paid/failed/rejected by an admin — while the ledger
only cares about the net effect (funds out on accept, funds back on reverse).
"""

from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel

# Minimum withdrawal, fixed in service + DB constraint to keep the rule in one
# place that no view or serializer can silently bypass.
MIN_WITHDRAWAL_AMOUNT = Decimal("500.00")


class WithdrawalRequest(TimeStampedModel):
    """A user-facing payout request awaiting admin action.

    ``status`` drives the workflow:

    PENDING -> PROCESSING -> COMPLETED
    PENDING -> REJECTED
    PROCESSING -> FAILED | REJECTED
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REJECTED = "rejected", "Rejected"

    class Provider(models.TextChoices):
        MPESA = "mpesa", "M-Pesa"
        TIGO_PESA = "tigo_pesa", "Tigo Pesa"
        AIRTEL_MONEY = "airtel_money", "Airtel Money"
        HALOPESA = "halopesa", "Halopesa"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="withdrawal_requests",
        db_index=True,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    mobile_money_number = models.CharField(max_length=32)
    provider = models.CharField(max_length=20, choices=Provider.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    reference = models.CharField(
        max_length=40,
        unique=True,
        help_text="Stable code shared with the ledger rows for this payout.",
    )
    admin_notes = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    # ClickPesa disbursement result (Prompt 12 auto-payout).
    # ``payout_status`` reflects the gateway's payout state (SUCCESS / AUTHORIZED
    # / FAILED / PENDING / UNAVAILABLE). UNAVAILABLE = payouts not provisioned
    # on the account or a provider/config error, so the admin can still record
    # the completion manually in demo mode.
    payout_reference = models.CharField(
        max_length=64, blank=True, default="",
        help_text="ClickPesa payout id returned by the gateway.",
    )
    payout_status = models.CharField(
        max_length=32, blank=True, default="",
        help_text="ClickPesa payout status: SUCCESS, AUTHORIZED, FAILED, "
        "PENDING or UNAVAILABLE when the gateway could not be used.",
    )
    payout_message = models.TextField(
        blank=True, default="",
        help_text="Human-readable message/notes returned by the payout call.",
    )

    class Meta:
        verbose_name = "Withdrawal request"
        verbose_name_plural = "Withdrawal requests"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "status"], name="wd_user_status_idx"),
            models.Index(fields=["status", "created_at"], name="wd_status_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=MIN_WITHDRAWAL_AMOUNT),
                name="wd_amount_minimum",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_status_display()} {self.amount} ({self.user_id})"