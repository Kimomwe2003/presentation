"""Wallet business logic (Prompt 10).

The ledger is the source of truth; ``Wallet.balance`` is a cache that is
recomputed (reconciled) inside the same transaction that writes ledger rows, so
it can never silently drift from the ledger.

Every mutation here:

- runs inside ``transaction.atomic()`` and takes ``select_for_update`` on the
  affected ``Wallet`` row, serializing concurrent writers on the same user;
- is the only code path that changes a balance — no view or serializer does;
- treats money exclusively as ``Decimal`` — ``float`` inputs are rejected.

The 6% platform fee is charged once per completed sale: a ``PLATFORM_FEE`` row
(accounting) and a ``CREDIT`` row for the net earnings are created together,
guarded by both a service-level check and the ``(order_item, type)`` unique
constraint, so re-processing the same item is a no-op.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum

from orders.models import Order, OrderItem

from .models import LedgerTransaction, Wallet

PLATFORM_FEE_RATE = Decimal("0.06")
CURRENCY_PRECISION = Decimal("0.01")

# Types whose COMPLETED rows sum to the wallet balance. PAYMENT and
# PLATFORM_FEE are informational accounting entries excluded from the sum.
BALANCE_AFFECTING_TYPES = (
    LedgerTransaction.Type.CREDIT,
    LedgerTransaction.Type.DEBIT,
    LedgerTransaction.Type.WITHDRAWAL,
    LedgerTransaction.Type.REFUND,
    LedgerTransaction.Type.ADJUSTMENT,
)


class WalletError(Exception):
    """Base class for wallet domain errors."""


class InsufficientBalance(WalletError):
    """Raised when a debit would take the wallet below zero."""


def _as_decimal(value) -> Decimal:
    """Coerce money input to Decimal, rejecting floats on principle."""
    if isinstance(value, float):
        raise WalletError("Money must be a Decimal, never a float.")
    return Decimal(str(value))


def reconcile_balance(user) -> Decimal:
    """Sum of the user's COMPLETED, balance-affecting ledger rows.

    This is the source-of-truth figure; ``Wallet.balance`` mirrors it.
    """
    total = (
        LedgerTransaction.objects.filter(
            user=user,
            status=LedgerTransaction.Status.COMPLETED,
            type__in=BALANCE_AFFECTING_TYPES,
        ).aggregate(total=Sum("amount"))["total"]
    )
    return (total if total is not None else Decimal("0.00")).quantize(CURRENCY_PRECISION)


def _sync_wallet_balance(wallet: Wallet) -> None:
    """Refresh the cached balance from the ledger (caller holds the wallet lock)."""
    wallet.balance = reconcile_balance(wallet.user)
    wallet.save(update_fields=["balance", "updated_at"])


class WalletService:
    """Verified-event gateway to wallet balances. No serializer may touch these."""

    @staticmethod
    def process_completed_sale(
        order_item: OrderItem,
    ) -> tuple[LedgerTransaction, LedgerTransaction] | None:
        """Credit a seller's wallet for a completed sale, minus the 6% fee.

        Atomic and idempotent:
        - The seller's wallet row is locked for the duration, so two concurrent
          completions of the same item serialize; the second call finds the
          existing rows and returns them (no-op).
        - The ``(order_item, type)`` unique constraint is a second, DB-level
          guarantee that only one fee/credit pair ever exists per item.

        Returns ``None`` when the item has no seller to credit.
        """
        seller_id = order_item.seller_id
        if seller_id is None:
            return None
        line_total = order_item.line_total

        with transaction.atomic():
            wallet = (
                Wallet.objects.select_for_update().get_or_create(user_id=seller_id)[0]
            )
            existing_fee = LedgerTransaction.objects.filter(
                order_item_id=order_item.pk,
                type=LedgerTransaction.Type.PLATFORM_FEE,
            ).first()
            if existing_fee is not None:
                credit = LedgerTransaction.objects.get(
                    order_item_id=order_item.pk,
                    type=LedgerTransaction.Type.CREDIT,
                )
                return existing_fee, credit

            fee = (line_total * PLATFORM_FEE_RATE).quantize(
                CURRENCY_PRECISION, rounding=ROUND_HALF_UP
            )
            net = (line_total - fee).quantize(CURRENCY_PRECISION)

            reference = f"order-item:{order_item.pk}"
            fee_row = LedgerTransaction.objects.create(
                user_id=seller_id,
                amount=-fee,
                type=LedgerTransaction.Type.PLATFORM_FEE,
                status=LedgerTransaction.Status.COMPLETED,
                order_item_id=order_item.pk,
                reference=reference,
                description=f"Platform fee for sale of {order_item.product_name}",
            )
            credit_row = LedgerTransaction.objects.create(
                user_id=seller_id,
                amount=net,
                type=LedgerTransaction.Type.CREDIT,
                status=LedgerTransaction.Status.COMPLETED,
                order_item_id=order_item.pk,
                reference=reference,
                description=f"Net earnings from sale of {order_item.product_name}",
            )
            _sync_wallet_balance(wallet)
        return fee_row, credit_row

    @staticmethod
    def credit(
        user,
        amount,
        *,
        type_: str = LedgerTransaction.Type.CREDIT,
        reference: str = "",
        description: str = "",
    ) -> LedgerTransaction:
        """Add a positive amount to a user's balance (e.g. a refund repayment).

        ``type_`` defaults to CREDIT; withdrawal reversals (Prompt 12) pass
        REFUND so the ledger distinguishes a refund from ordinary earnings.
        """
        amount = _as_decimal(amount).quantize(CURRENCY_PRECISION, rounding=ROUND_HALF_UP)
        if amount < 0:
            raise WalletError("Credit amount must be non-negative.")
        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get_or_create(user=user)[0]
            row = LedgerTransaction.objects.create(
                user=user,
                amount=amount,
                type=type_,
                status=LedgerTransaction.Status.COMPLETED,
                reference=reference,
                description=description,
            )
            _sync_wallet_balance(wallet)
        return row

    @staticmethod
    def refund(
        user,
        amount,
        *,
        reference: str = "",
        description: str = "",
    ) -> LedgerTransaction:
        """Restore money to a balance, recorded as a REFUND ledger row.

        Used to reverse a failed/rejected withdrawal (Prompt 12). The refund is
        written in the same transaction as the request's status change, so a
        rejected withdrawal can never leave the user's balance inconsistent.
        """
        return WalletService.credit(
            user,
            amount,
            type_=LedgerTransaction.Type.REFUND,
            reference=reference,
            description=description,
        )

    @staticmethod
    def debit(
        user,
        amount,
        *,
        type_: str = LedgerTransaction.Type.DEBIT,
        reference: str = "",
        description: str = "",
    ) -> LedgerTransaction:
        """Remove money from a user's balance, rejecting over-debits server-side.

        ``type_`` defaults to DEBIT; withdrawals (Prompt 12) pass WITHDRAWAL.
        """
        amount = _as_decimal(amount).quantize(CURRENCY_PRECISION, rounding=ROUND_HALF_UP)
        if amount < 0:
            raise WalletError("Debit amount must be non-negative.")
        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get_or_create(user=user)[0]
            available = reconcile_balance(user)
            if available < amount:
                raise InsufficientBalance(
                    "Insufficient wallet balance for this debit "
                    f"({available} available, {amount} requested)."
                )
            row = LedgerTransaction.objects.create(
                user=user,
                amount=-amount,
                type=type_,
                status=LedgerTransaction.Status.COMPLETED,
                reference=reference,
                description=description,
            )
            _sync_wallet_balance(wallet)
        return row

    @staticmethod
    def balance_summary(user) -> dict:
        """Available balance plus lifetime earnings/withdrawal totals.

        ``total_withdrawn`` reads zero until Prompt 12 adds the withdrawal flow.
        """
        wallet = Wallet.objects.get_or_create(user=user)[0]
        earnings = (
            LedgerTransaction.objects.filter(
                user=user,
                status=LedgerTransaction.Status.COMPLETED,
                type=LedgerTransaction.Type.CREDIT,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        withdrawn = (
            LedgerTransaction.objects.filter(
                user=user,
                status=LedgerTransaction.Status.COMPLETED,
                type=LedgerTransaction.Type.WITHDRAWAL,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        return {
            "balance": wallet.balance,
            "total_earnings": earnings.quantize(CURRENCY_PRECISION),
            # Withdrawals are recorded as negative amounts; report the positive total.
            "total_withdrawn": (-withdrawn).quantize(CURRENCY_PRECISION),
        }

    @staticmethod
    def pending_earnings(user) -> Decimal:
        """Net (post-fee) value of the user's sold-but-not-yet-completed items.

        "Sold" means the order is PAID (the only envelope state in the normal
        flow between payment and completion) and the item is still in
        fulfillment — not yet COMPLETED and not CANCELLED. The figure is the
        projected 94% the seller would receive once each item completes, so the
        Earnings screen can separate "in hand" (wallet balance) from "in
        transit" (this). Read-only: no wallet rows are written.
        """
        total = (
            OrderItem.objects.filter(
                seller=user,
                order__status=Order.Status.PAID,
            )
            .exclude(
                item_status__in=(
                    OrderItem.Status.COMPLETED,
                    OrderItem.Status.CANCELLED,
                )
            )
            .aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F("unit_price")
                        * F("quantity")
                        * (Decimal("1") - PLATFORM_FEE_RATE),
                        output_field=DecimalField(max_digits=12, decimal_places=4),
                    )
                )
            )["total"]
        )
        return (total if total is not None else Decimal("0.00")).quantize(
            CURRENCY_PRECISION, rounding=ROUND_HALF_UP
        )
