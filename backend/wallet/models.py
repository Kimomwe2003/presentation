"""Wallet + ledger models (Prompt 10).

Design decision — the ledger is the source of truth:

- Every balance change is a :class:`LedgerTransaction` row; ``Wallet.balance``
  is a *cached* value recomputed from the ledger inside the same transaction
  by :mod:`wallet.services` (documented in docs/ARCHITECTURE.md).
- No view or serializer writes ``balance``; it is only ever refreshed through
  ``WalletService`` after a verified event (a completed sale, and later a
  withdrawal, refund or adjustment).
- A DB check constraint guarantees the cached balance never goes negative,
  and a unique ``(order_item, type)`` constraint makes sale crediting
  idempotent at the database level.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models

from orders.models import OrderItem


class Wallet(models.Model):
    """Cached, reconciled balance for a user's earnings.

    ``balance`` must never be edited directly by a serializer or admin form —
    it is refreshed by :func:`wallet.services.reconcile_balance` inside the
    transaction that wrote the ledger rows it summarizes.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wallet"
        verbose_name_plural = "Wallets"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(balance__gte=Decimal("0.00")),
                name="wallet_balance_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"Wallet({self.user_id}) balance={self.balance}"


class LedgerTransaction(models.Model):
    """One signed movement on a user's ledger.

    ``amount`` is signed: positive = money added to the user's spendable
    balance, negative = money removed. Rows whose ``type`` is balance-affecting
    (CREDIT/DEBIT/WITHDRAWAL/REFUND/ADJUSTMENT) and ``status`` is COMPLETED are
    summed to compute the wallet balance; PAYMENT and PLATFORM_FEE rows are
    informational accounting entries and are excluded from that sum (the net
    CREDIT already reflects the fee).
    """

    class Type(models.TextChoices):
        CREDIT = "credit", "Credit"
        DEBIT = "debit", "Debit"
        PLATFORM_FEE = "platform_fee", "Platform fee"
        WITHDRAWAL = "withdrawal", "Withdrawal"
        REFUND = "refund", "Refund"
        PAYMENT = "payment", "Payment"
        ADJUSTMENT = "adjustment", "Adjustment"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ledger_transactions",
        db_index=True,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=20, choices=Type.choices, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
        db_index=True,
    )
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_transactions",
    )
    reference = models.CharField(
        max_length=128,
        blank=True,
        help_text="Free-text reference, e.g. 'order-item:42' or a provider reference.",
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ledger transaction"
        verbose_name_plural = "Ledger transactions"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "created_at"], name="ledger_user_created_idx"),
            models.Index(fields=["reference"], name="ledger_reference_idx"),
        ]
        constraints = [
            # Idempotency at the DB level: at most one row of a given type per
            # order item (one PLATFORM_FEE + one CREDIT per completed sale).
            # NULL order_item rows are unaffected (Postgres treats NULLs as
            # distinct in unique constraints).
            models.UniqueConstraint(
                fields=["order_item", "type"],
                name="ledger_unique_order_item_type",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_type_display()} {self.amount} ({self.user_id})"
