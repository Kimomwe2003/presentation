"""Reconcile stuck payments against the ClickPesa gateway (missed-webhook safety net).

Run:  python manage.py reconcile_payments [--window-minutes 5] [--max 50] [--dry-run]

ClickPesa webhooks are reliable but no gateway guarantees 100% delivery. This
command queries ClickPesa's own transaction-status API directly for any
``Payment`` still in ``pending`` past a short window, and corrects local state
to whatever the gateway actually reports — so a dropped webhook can't strand a
completed payment or hide a real failure.

Design rules (mirrors the FastAPI reference in zanelimu_platform):
- Only payments in a non-terminal state (PENDING) are touched; anything the
  webhook already resolved is left alone.
- If the gateway still reports the payment in-progress, nothing changes.
- If the gateway has no record of the reference, nothing changes (a future
  expiry/abandonment pass can deal with it).
- A terminal status from the gateway is applied exactly as the webhook would
  have applied it (including the same notification + audit side effects).

Scheduling: ideally every few minutes via cron, e.g.
  */5 * * * *  cd /path/backend && venv/bin/python manage.py reconcile_payments
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from payments.models import Payment
from payments.services import payment_service
from payments.services.clickpesa_service import ClickPesaService


class Command(BaseCommand):
    help = "Reconcile pending ClickPesa payments against the gateway."

    def add_arguments(self, parser):
        parser.add_argument(
            "--window-minutes",
            type=int,
            default=5,
            help="Only pending payments older than this many minutes are checked.",
        )
        parser.add_argument(
            "--max",
            type=int,
            default=50,
            help="Cap the number of payments reconciled per run.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be reconciled without calling the gateway.",
        )

    def handle(self, *args, **options):
        window_minutes = options["window_minutes"]
        max_count = options["max"]
        dry_run = options["dry_run"]

        cutoff = timezone.now() - timezone.timedelta(minutes=window_minutes)
        pending = (
            Payment.objects.select_related("order")
            .filter(status=Payment.Status.PENDING, created_at__lt=cutoff)
            .order_by("created_at")[:max_count]
        )

        service = ClickPesaService() if not dry_run else None
        stats = {"checked": 0, "completed": 0, "failed": 0, "pending": 0, "errors": 0}

        for payment in pending:
            stats["checked"] += 1
            if dry_run:
                self.stdout.write(f"  [dry-run] would check {payment.external_reference}")
                continue
            try:
                outcome = reconcile_one(payment, service)
                stats[outcome] += 1
            except Exception:  # noqa: BLE001 - one bad attempt must not abort the run
                stats["errors"] += 1
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f"Reconciled: checked={stats['checked']} completed={stats['completed']} "
                f"failed={stats['failed']} pending={stats['pending']} errors={stats['errors']}"
            )
        )


def reconcile_one(payment: Payment, service: ClickPesaService) -> str:
    """Query the gateway for a single payment and apply its remote state.

    Returns the canonical outcome: ``completed``|``failed``|``pending``.
    """
    from payments.services.clickpesa_service import parse_payment_status_response

    results = service.query_payment_status(payment.external_reference)
    entry = results[0] if isinstance(results, list) and results else (results or {})
    if not entry:
        return "pending"  # gateway has no terminal answer yet

    with transaction.atomic():
        locked = Payment.objects.select_for_update().get(pk=payment.pk)
        if locked.status != Payment.Status.PENDING:
            return "pending"  # a webhook already resolved it mid-run

        canonical, gateway_message = parse_payment_status_response(entry)
        outcome = canonical or "pending"
        if outcome not in ("completed", "failed"):
            # Refresh the stored raw payload but stay pending.
            locked.raw_provider_response = entry
            locked.save(update_fields=["raw_provider_response", "updated_at"])
            return "pending"

        locked.raw_provider_response = entry
        payment_service._apply_tx_fields(locked, entry)
        if outcome == "completed":
            if not payment_service._amount_matches(locked, entry.get("collectedAmount")):
                locked.status = Payment.Status.FAILED
                locked.failure_reason = "Amount mismatch"
                locked.save(
                    update_fields=[
                        "status",
                        "failure_reason",
                        "clickpesa_transaction_id",
                        "raw_provider_response",
                        "updated_at",
                    ]
                )
                payment_service._notify_payment(locked, Payment.Status.FAILED)
                return "failed"
            locked.status = Payment.Status.SUCCESSFUL
            locked.save(
                update_fields=[
                    "status",
                    "clickpesa_transaction_id",
                    "raw_provider_response",
                    "updated_at",
                ]
            )
            payment_service._mark_paid_if_possible(locked.order)
            return "completed"

        locked.status = Payment.Status.FAILED
        locked.failure_reason = locked.failure_reason or str(gateway_message or "")
        locked.save(
            update_fields=[
                "status",
                "clickpesa_transaction_id",
                "failure_reason",
                "raw_provider_response",
                "updated_at",
            ]
        )
        payment_service._fail_order_if_possible(locked.order)
        return "failed"
