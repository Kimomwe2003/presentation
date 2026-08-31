"""Withdrawal business logic (Prompt 12).

Design decision — handling of the reserved amount
--------------------------------------------------

The wallet ledger is the source of truth: balance = sum of COMPLETED
balance-affecting rows. We make the withdrawal a **hard debit at request time**
(a COMPLETED WITHDRAWAL row, negative amount) rather than a separate "held"
field. This:

- Reuses the existing invariant — ``Wallet.balance`` never goes negative (a DB
  check constraint) and ``WalletService.debit`` rejects over-debits server-side.
- Immediately reserves the funds: the moment a request is accepted the amount
  leaves the spendable balance, so it cannot be double-spent.
- Reverses cleanly on FAILED/REJECTED: a **REFUND** ledger row (positive,
  COMPLETED) is written in the *same transaction* as the request's status
  change, restoring the exact amount. The reversal is atomic and exact — a
  failed/rejected withdrawal can never leave the balance inconsistent.

Consequence: "available balance" already excludes money sitting in an in-flight
withdrawal, and ``balance_summary.total_withdrawn`` (sum of COMPLETED WITHDRAWAL
rows) reflects successfully-confirmed payouts.

Every mutation here runs inside ``transaction.atomic()`` and takes
``select_for_update`` on the affected rows, serializing concurrent actors.
"""

from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from wallet.models import LedgerTransaction
from wallet.services import InsufficientBalance as WalletInsufficientBalance
from wallet.services import WalletService

from .models import MIN_WITHDRAWAL_AMOUNT, WithdrawalRequest
from .payout import WithdrawalPayoutService

CURRENCY_PRECISION = Decimal("0.01")


class WithdrawalError(Exception):
    """Base class for withdrawal domain errors."""


class InsufficientBalance(WithdrawalError):
    """Raised when the wallet cannot cover the requested withdrawal."""


class TransitionDenied(WithdrawalError):
    """Raised for an illegal status transition or non-staff actor.

    ``code`` lets views map to a 400 (invalid transition) or 403 (not allowed).
    """

    def __init__(self, message: str, code: str = "invalid_transition"):
        super().__init__(message)
        self.code = code


class WithdrawalService:
    """Only sanctioned code path that moves money for a withdrawal."""

    # Allowed transitions, used to reject illegal moves before touching anything.
    NEXT = {
        WithdrawalRequest.Status.PENDING: {
            WithdrawalRequest.Status.PROCESSING,
            WithdrawalRequest.Status.REJECTED,
        },
        WithdrawalRequest.Status.PROCESSING: {
            WithdrawalRequest.Status.COMPLETED,
            WithdrawalRequest.Status.FAILED,
            WithdrawalRequest.Status.REJECTED,
        },
        WithdrawalRequest.Status.COMPLETED: set(),
        WithdrawalRequest.Status.FAILED: set(),
        WithdrawalRequest.Status.REJECTED: set(),
    }

    # Statuses that give the money back.
    REVERSAL_STATUSES = {
        WithdrawalRequest.Status.FAILED,
        WithdrawalRequest.Status.REJECTED,
    }

    @staticmethod
    def _generate_reference() -> str:
        return f"WD-{uuid4().hex[:12].upper()}"

    @staticmethod
    def request_withdrawal(
        user,
        *,
        amount,
        provider: str,
        mobile_money_number: str,
    ) -> WithdrawalRequest:
        """Atomically create a request and reserve its amount from the wallet.

        Raises :class:`InsufficientBalance` or :class:`WithdrawalError` on a
        bad request. On success the user's balance is reduced by ``amount`` and
        a PENDING request exists for the admin queue.
        """
        if isinstance(amount, float):
            raise WithdrawalError("Money must be a Decimal, never a float.")
        amount = Decimal(str(amount)).quantize(
            CURRENCY_PRECISION, rounding=ROUND_HALF_UP
        )
        if amount < MIN_WITHDRAWAL_AMOUNT:
            raise WithdrawalError(
                f"Minimum withdrawal is {MIN_WITHDRAWAL_AMOUNT}."
            )

        reference = WithdrawalService._generate_reference()

        with transaction.atomic():
            request = WithdrawalRequest.objects.create(
                user=user,
                amount=amount,
                provider=provider,
                mobile_money_number=mobile_money_number,
                status=WithdrawalRequest.Status.PENDING,
                reference=reference,
            )
            try:
                WalletService.debit(
                    user,
                    amount,
                    type_=LedgerTransaction.Type.WITHDRAWAL,
                    reference=f"withdrawal:{reference}",
                    description=(
                        f"Payout of {amount} to {provider} {mobile_money_number}"
                    ),
                )
            except WalletInsufficientBalance:
                # The whole block rolls back (leaving no orphan request) but we
                # still surface a domain-meaningful error to the caller.
                raise InsufficientBalance(
                    "Insufficient wallet balance for this withdrawal."
                ) from None
        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=user,
            action=AuditLogService.Action.WITHDRAWAL_REQUEST,
            target=request,
            description=(
                f"Withdrawal {request.reference} of {amount} requested "
                f"({provider})"
            ),
            after={"amount": str(amount), "status": request.status},
        )
        return request

    @staticmethod
    def transition(
        request: WithdrawalRequest,
        *,
        to: str,
        actor,
        admin_notes: str = "",
    ) -> WithdrawalRequest:
        """Move a request to ``to``, reversing the funds if ``to`` is a reversal.

        Only staff may act. The transition table rejects illegal moves; the row
        is locked so two concurrent admins cannot both move the same request.
        """
        if not getattr(actor, "is_staff", False):
            raise TransitionDenied(
                "Only staff can update withdrawal requests.",
                code="permission_denied",
            )

        with transaction.atomic():
            locked = (
                WithdrawalRequest.objects.select_for_update().get(pk=request.pk)
            )
            if to not in WithdrawalService.NEXT[locked.status]:
                raise TransitionDenied(
                    f"Cannot move a {locked.get_status_display()} withdrawal "
                    f"to {to}."
                )

            if to in WithdrawalService.REVERSAL_STATUSES:
                WalletService.refund(
                    locked.user,
                    locked.amount,
                    reference=f"withdrawal:{locked.reference}",
                    description=(
                        f"Refund for {locked.get_status_display()} withdrawal "
                        f"{locked.reference}"
                    ),
                )

            locked.status = to
            if admin_notes:
                locked.admin_notes = admin_notes
            if to in (
                WithdrawalRequest.Status.COMPLETED,
                WithdrawalRequest.Status.FAILED,
                WithdrawalRequest.Status.REJECTED,
            ):
                locked.processed_at = timezone.now()
            locked.save(update_fields=["status", "admin_notes", "processed_at"])
        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=actor,
            action=AuditLogService.Action.WITHDRAWAL_TRANSITION,
            target=locked,
            description=(
                f"Withdrawal {locked.reference} → {to} "
                f"{('(' + admin_notes + ')') if admin_notes else ''}"
            ),
            after={"status": to},
        )
        _notify_status_change(locked)

        # On a successful completion, push the money to the seller's wallet via
        # ClickPesa (best-effort; the gateway result is recorded on the row and
        # never blocks or reverses the COMPLETED transition).
        if to == WithdrawalRequest.Status.COMPLETED:
            WithdrawalPayoutService.attempt(locked)
            locked.refresh_from_db(fields=[
                "payout_reference", "payout_status", "payout_message"
            ])

        return locked

    @staticmethod
    def process(request: WithdrawalRequest, *, actor, admin_notes: str = ""):
        return WithdrawalService.transition(
            request,
            to=WithdrawalRequest.Status.PROCESSING,
            actor=actor,
            admin_notes=admin_notes,
        )

    @staticmethod
    def complete(request: WithdrawalRequest, *, actor, admin_notes: str = ""):
        return WithdrawalService.transition(
            request,
            to=WithdrawalRequest.Status.COMPLETED,
            actor=actor,
            admin_notes=admin_notes,
        )

    @staticmethod
    def fail(request: WithdrawalRequest, *, actor, admin_notes: str = ""):
        return WithdrawalService.transition(
            request,
            to=WithdrawalRequest.Status.FAILED,
            actor=actor,
            admin_notes=admin_notes,
        )

    @staticmethod
    def reject(request: WithdrawalRequest, *, actor, admin_notes: str = ""):
        return WithdrawalService.transition(
            request,
            to=WithdrawalRequest.Status.REJECTED,
            actor=actor,
            admin_notes=admin_notes,
        )


def _notify_status_change(request: WithdrawalRequest) -> None:
    """Best-effort in-app notification for the requester on a status change."""
    from notifications.services import NotificationService

    NotificationService.notify(
        user=request.user,
        type_="withdrawal_update",
        title=f"Withdrawal {request.get_status_display()}",
        body=(
            f"Withdrawal {request.reference} of {request.amount} is now "
            f"{request.get_status_display()}."
        ),
        related_object=request,
    )
