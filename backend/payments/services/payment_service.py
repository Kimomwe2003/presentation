"""Payment business logic (Prompt 09).

Separated from :mod:`payments.services.clickpesa_service` per the master spec:

- :class:`ClickPesaService` — raw API calls only (no decisions).
- This module — decides what a ClickPesa result means, keeps ``Payment`` rows
  consistent, and is the **only** path that moves an order to ``PAID`` via a
  verified payment event.

Every order transition goes through ``orders.services.transition_order`` with
``actor="payment"``; the state machine remains the single source of truth.
"""

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction

from orders.models import Order
from orders.services import transition_order
from orders.state_machine import (
    ACTION_FAIL_PAYMENT,
    ACTION_MARK_PAID,
    ACTION_RETRY_PAYMENT,
    TransitionDenied,
)

from ..checksum import verify_payload_checksum
from ..models import Payment
from .clickpesa_service import (
    ClickPesaError,
    ClickPesaService,
    extract_transaction_id,
    normalize_payment_status,
    parse_payment_status_response,
)

# Canonical ClickPesa statuses (see clickpesa_service.normalize_payment_status).
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUS_PENDING = "pending"

_WEBHOOK_PATH = "/api/clickpesa/webhook/"


class PaymentError(Exception):
    """User-facing payment error (bad order state, provider failure, ...)."""


class WebhookSignatureError(Exception):
    """Raised when an inbound webhook has a missing/invalid checksum."""


# ---------------------------------------------------------------------------
# Status interpretation
# ---------------------------------------------------------------------------


def interpret_remote_status(clickpesa_status: str | None) -> str:
    """Map a raw ClickPesa status string onto our :class:`Payment.Status` value.

    Uses canonical normalization so many gateway spellings
    (``SUCCESS``/``PAYMENT SUCCESSFUL``/``COMPLETED``, ``FAILED``/``DECLINED``/
    ``INSUFFICIENT FUNDS``, ``CANCELLED``/``ABORTED``, ...) all resolve.
    """
    canonical = normalize_payment_status(clickpesa_status)
    if canonical == STATUS_COMPLETED:
        return Payment.Status.SUCCESSFUL
    if canonical in (STATUS_FAILED, STATUS_CANCELLED):
        return Payment.Status.FAILED
    return Payment.Status.PENDING  # pending / processing / unknown


def _amount_matches(payment: Payment, collected_amount) -> bool:
    """True when the collected amount is missing/zero or equals the order total."""
    if collected_amount in (None, "", 0, "0", "0.00"):
        return True  # no collection info yet — not a fraud signal
    try:
        collected = Decimal(str(collected_amount))
    except (InvalidOperation, ValueError):
        return False
    return collected == payment.amount


# ---------------------------------------------------------------------------
# Initiation / retry
# ---------------------------------------------------------------------------


def _next_reference(order: Order) -> str:
    """Alphanumeric, unique-per-attempt ClickPesa orderReference (max 20 chars).

    Format: RH + first 10 chars of order_number + attempt digit.
    e.g. RHD99EC64B51
    """
    attempt = Payment.objects.filter(order=order).count() + 1
    short_order = order.order_number[:10]
    return f"RH{short_order}{attempt}"


def _transition_order(order: Order, action: str) -> None:
    transition_order(order, action, actor="payment")

def _mark_paid_if_possible(order: Order) -> None:
    try:
        _transition_order(order, ACTION_MARK_PAID)
    except TransitionDenied:
        pass  # already PAID (e.g., another attempt won the race) — idempotent


def _fail_order_if_possible(order: Order) -> None:
    try:
        _transition_order(order, ACTION_FAIL_PAYMENT)
    except TransitionDenied:
        pass  # no longer PENDING_PAYMENT — nothing to fail


def initiate_payment(
    order: Order, phone_number: str, *, service: ClickPesaService | None = None
) -> Payment:
    """Create a PENDING Payment and start a ClickPesa USSD-PUSH attempt.

    Supports retry: when the order is ``PAYMENT_FAILED`` it is moved back to
    ``PENDING_PAYMENT`` (retry_payment transition) and any older ``PENDING``
    attempts on the order are expired.
    """
    if order.status not in (Order.Status.PENDING_PAYMENT, Order.Status.PAYMENT_FAILED):
        raise PaymentError("This order cannot be paid from its current status.")
    if not phone_number:
        raise PaymentError("A phone number is required to receive the USSD payment prompt.")

    service = service or ClickPesaService()

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status == Order.Status.PAYMENT_FAILED:
            _transition_order(order, ACTION_RETRY_PAYMENT)
        Payment.objects.filter(order=order, status=Payment.Status.PENDING).update(
            status=Payment.Status.EXPIRED
        )
        reference = _next_reference(order)
        payment = Payment.objects.create(
            order=order,
            amount=order.total,
            external_reference=reference,
        )

    # The provider call happens after the payment row is committed so a failed
    # attempt is persisted even though the request to the client errors.
    try:
        # Preview first to validate phone number and check network availability
        try:
            preview = service.preview_ussd_push(
                amount=str(order.total),
                order_reference=reference,
                phone_number=phone_number,
            )
            # Check if the target network is available
            if isinstance(preview, dict):
                active_methods = preview.get("activeMethods") or []
                for method in active_methods:
                    if method.get("status") == "UNAVAILABLE":
                        net_name = method.get("name", "Network")
                        msg = method.get("message") or f"{net_name} is unavailable"
                        raise ClickPesaError(
                            f"Network unavailable: {msg}",
                            status_code=400,
                            response=preview,
                        )
        except ClickPesaError:
            raise  # re-raise our own errors
        except Exception:
            pass  # preview is optional — proceed even if it fails

        response = service.initiate_ussd_push(
            amount=str(order.total),
            order_reference=reference,
            phone_number=phone_number,
            webhook_url=_webhook_url(),
        )
    except ClickPesaError as exc:
        payment.status = Payment.Status.FAILED
        payment.failure_reason = str(exc)
        payment.raw_provider_response = exc.response if exc.response else {"error": str(exc)}
        payment.save(
            update_fields=["status", "failure_reason", "raw_provider_response", "updated_at"]
        )
        # Log the full ClickPesa error for debugging
        import logging as _log
        _err_log = _log.getLogger("payments.error")
        _err_log.error(
            "ClickPesa USSD push FAILED | ref=%s phone=%s amount=%s | HTTP %s | resp=%s",
            reference, phone_number, order.total,
            exc.status_code, exc.response,
        )
        # Extract the actual ClickPesa error message if available
        clickpesa_msg = ""
        if isinstance(exc.response, dict):
            clickpesa_msg = exc.response.get("message", "")
        elif isinstance(exc.response, str):
            clickpesa_msg = exc.response
        if clickpesa_msg:
            raise PaymentError(f"ClickPesa: {clickpesa_msg}") from exc
        raise PaymentError(
            f"ClickPesa could not start the payment. "
            f"(HTTP {exc.status_code or 'error'})"
        ) from exc

    payment.raw_provider_response = response or {}
    _apply_remote_status(payment)
    _audit_payment_initiation(payment)
    return payment


def _webhook_url() -> str | None:
    """Public webhook callback for ClickPesa, from settings (None if unset)."""
    base = getattr(settings, "CLICKPESA_WEBHOOK_BASE_URL", "") or ""
    return (base.rstrip("/") + _WEBHOOK_PATH) if base else None


def _apply_remote_status(payment: Payment) -> None:
    """Apply a ClickPesa status dict (already stored on the payment) to our state."""
    from auditlog.services import AuditLogService

    response = payment.raw_provider_response
    # Persist the gateway's transaction id and channel for later correlation.
    if isinstance(response, dict):
        tx_id = extract_transaction_id(response)
        if tx_id and not payment.clickpesa_transaction_id:
            payment.clickpesa_transaction_id = str(tx_id)
        channel = response.get("channel")
        if channel and not payment.network_channel:
            payment.network_channel = str(channel).strip().upper()

    status = interpret_remote_status(response.get("status") if isinstance(response, dict) else None)
    update_fields = ["status", "clickpesa_transaction_id", "network_channel", "updated_at"]
    if status == Payment.Status.SUCCESSFUL:
        payment.status = Payment.Status.SUCCESSFUL
        payment.save(update_fields=update_fields)
        _mark_paid_if_possible(payment.order)
        AuditLogService.log(
            actor=None,
            action=AuditLogService.Action.PAYMENT_SUCCESS,
            target=payment,
            description=f"Payment {payment.external_reference} succeeded",
            after={"amount": str(payment.amount), "order": payment.order_id},
        )
    elif status == Payment.Status.FAILED:
        if isinstance(response, dict) and response.get("message"):
            payment.failure_reason = str(response["message"])
        payment.status = Payment.Status.FAILED
        payment.save(
            update_fields=[
                "status",
                "clickpesa_transaction_id",
                "failure_reason",
                "network_channel",
                "updated_at",
            ]
        )
        _fail_order_if_possible(payment.order)
        AuditLogService.log(
            actor=None,
            action=AuditLogService.Action.PAYMENT_FAILURE,
            target=payment,
            description=f"Payment {payment.external_reference} failed",
            after={"amount": str(payment.amount), "order": payment.order_id},
        )
    else:
        payment.status = Payment.Status.PENDING
        payment.save(
            update_fields=[
                "status",
                "clickpesa_transaction_id",
                "network_channel",
                "raw_provider_response",
                "updated_at",
            ]
        )


def _notify_payment(payment: Payment, outcome: str) -> None:
    """Create an in-app notification for the buyer when a payment resolves.

    Best-effort and never raises. This is the real-time surface the mobile app
    polls (it is delivered via the notifications endpoint alongside the payment
    status endpoint).
    """
    from notifications.models import Notification
    from notifications.services import NotificationService

    buyer = getattr(payment.order, "buyer", None)
    if buyer is None:
        return
    note_type = Notification.Type.PAYMENT_RESULT
    if outcome == Payment.Status.SUCCESSFUL:
        title = "Payment successful"
        body = f"Your payment for order {payment.order.order_number} was received."
    else:
        title = "Payment failed"
        reason = payment.failure_reason or ""
        body = (
            f"Your payment for order {payment.order.order_number} failed."
            f"{(' ' + reason) if reason else ''}"
        )
    NotificationService.notify(
        user=buyer, type_=note_type, title=title, body=body, related_object=payment
    )


def _audit_payment_initiation(payment: Payment) -> None:
    """Log a payment attempt with its outcome (best-effort)."""
    from auditlog.services import AuditLogService

    action = (
        AuditLogService.Action.PAYMENT_SUCCESS
        if payment.status == Payment.Status.SUCCESSFUL
        else AuditLogService.Action.PAYMENT_FAILURE
        if payment.status == Payment.Status.FAILED
        else AuditLogService.Action.PAYMENT_INITIATE
    )
    AuditLogService.log(
        actor=None,
        action=action,
        target=payment,
        description=(
            f"Payment {payment.external_reference} for order "
            f"{payment.order.order_number} initiated ({payment.status})"
        ),
        after={"amount": str(payment.amount), "order": payment.order_id, "status": payment.status},
    )


def _audit_payment_event(payment: Payment, action: str) -> None:
    """Log a webhook/verify-driven terminal payment event (best-effort)."""
    from auditlog.services import AuditLogService

    AuditLogService.log(
        actor=None,
        action=action,
        target=payment,
        description=(
            f"Payment {payment.external_reference} for order "
            f"{payment.order.order_number} → {payment.status}"
        ),
        after={"amount": str(payment.amount), "order": payment.order_id, "status": payment.status},
    )


# ---------------------------------------------------------------------------
# Webhook handling (idempotent, checksum-verified)
# ---------------------------------------------------------------------------


def handle_webhook(payload: dict) -> None:
    """Verify and process a ClickPesa webhook.

    - Rejects requests that fail checksum verification (raises WebhookSignatureError).
    - Idempotent: a payment already in a final state (SUCCESSFUL/FAILED/EXPIRED)
      is a no-op — nothing is transitioned or double-processed.
    - Amount mismatches are recorded as FAILED payments without touching the order.
    - Handles ``PAYMENT RECEIVED`` / ``PAYMENT FAILED`` / ``PAYMENT CANCELLED``
      (event names normalised across spellings) and resolves the attempt by our
      orderReference OR by the gateway transaction id.
    """
    secret = settings.CLICKPESA_WEBHOOK_SECRET
    if not secret:
        raise WebhookSignatureError("Webhook checksum secret is not configured.")
    if not verify_payload_checksum(secret, payload):
        raise WebhookSignatureError("Webhook checksum verification failed.")

    from auditlog.services import AuditLogService

    event = str(payload.get("event") or "").strip().replace("_", " ").upper()
    if event not in ("PAYMENT RECEIVED", "PAYMENT FAILED", "PAYMENT CANCELLED"):
        return  # unrelated event — acknowledge and ignore

    data = payload.get("data") or {}
    if not isinstance(data, dict):
        return

    reference = data.get("orderReference")
    if not reference:
        reference = data.get("paymentReference")
    if not reference:
        tx_id = data.get("id")
        if tx_id:
            match = (
                Payment.objects.filter(clickpesa_transaction_id=str(tx_id))
                .order_by("-created_at")
                .first()
            )
            if match is not None:
                reference = match.external_reference
    if not reference:
        return

    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update()
            .select_related("order")
            .filter(external_reference=reference)
            .first()
        )
        if payment is None:
            return  # unknown reference — acknowledged, nothing processed
        if payment.status != Payment.Status.PENDING:
            return  # already final — duplicate callback is a no-op
        payment.raw_provider_response = data

        logic_status = interpret_remote_status(data.get("status"))
        # "PAYMENT CANCELLED" events may omit a status field — treat as failed.
        if event == "PAYMENT CANCELLED":
            logic_status = Payment.Status.FAILED

        if logic_status == Payment.Status.SUCCESSFUL and event == "PAYMENT RECEIVED":
            if not _amount_matches(payment, data.get("collectedAmount")):
                payment.status = Payment.Status.FAILED
                payment.failure_reason = data.get("message") or "Amount mismatch"
                payment.save(
                    update_fields=[
                        "status",
                        "failure_reason",
                        "raw_provider_response",
                        "updated_at",
                    ]
                )
                _notify_payment(payment, Payment.Status.FAILED)
                _audit_payment_event(payment, AuditLogService.Action.PAYMENT_FAILURE)
                return
            payment.status = Payment.Status.SUCCESSFUL
            _apply_tx_fields(payment, data)
            payment.save(
                update_fields=(
                    "status",
                    "clickpesa_transaction_id",
                    "network_channel",
                    "raw_provider_response",
                    "updated_at",
                )
            )
            _mark_paid_if_possible(payment.order)
            _audit_payment_event(payment, AuditLogService.Action.PAYMENT_SUCCESS)
        elif logic_status == Payment.Status.FAILED:
            payment.status = Payment.Status.FAILED
            _apply_tx_fields(payment, data)
            payment.failure_reason = payment.failure_reason or str(data.get("message") or "")
            payment.save(
                update_fields=(
                    "status",
                    "clickpesa_transaction_id",
                    "failure_reason",
                    "network_channel",
                    "raw_provider_response",
                    "updated_at",
                )
            )
            _fail_order_if_possible(payment.order)
            _notify_payment(payment, Payment.Status.FAILED)
            _audit_payment_event(payment, AuditLogService.Action.PAYMENT_FAILURE)
        else:
            payment.save(update_fields=["raw_provider_response", "updated_at"])


def _apply_tx_fields(payment: Payment, data: dict) -> None:
    """Persist the gateway transaction id, channel, and message from a webhook payload."""
    tx_id = data.get("id")
    if tx_id and not payment.clickpesa_transaction_id:
        payment.clickpesa_transaction_id = str(tx_id)
    if not payment.failure_reason and isinstance(data.get("message"), str):
        payment.failure_reason = data["message"]
    channel = data.get("channel")
    if channel and not payment.network_channel:
        payment.network_channel = str(channel).strip().upper()


# ---------------------------------------------------------------------------
# Manual verification fallback (queries ClickPesa directly)
# ---------------------------------------------------------------------------


def verify_payment_status(order: Order, *, service: ClickPesaService | None = None) -> Payment:
    """Fallback for delayed/unavailable webhooks: query ClickPesa directly.

    Idempotent — once a payment is SUCCESSFUL it is returned as-is.
    """
    payment = (
        Payment.objects.filter(order=order).select_related("order").order_by("-created_at").first()
    )
    if payment is None:
        raise PaymentError("No payment attempt exists for this order.")
    if payment.status == Payment.Status.SUCCESSFUL:
        return payment

    service = service or ClickPesaService()
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status == Payment.Status.SUCCESSFUL:
            return payment
        try:
            results = service.query_payment_status(payment.external_reference)
        except ClickPesaError as exc:
            raise PaymentError("Could not reach ClickPesa to verify. Try again shortly.") from exc

    from auditlog.services import AuditLogService

    entry = results[0] if isinstance(results, list) and results else (results or {})
    if not entry:
        return payment  # no data yet — remains PENDING

    payment.raw_provider_response = entry
    canonical, gateway_message = parse_payment_status_response(entry)
    # Fall back to the old direct-status interpretation if the parser is unsure.
    logic_status = interpret_remote_status(canonical or entry.get("status"))
    if logic_status == Payment.Status.SUCCESSFUL:
        if not _amount_matches(payment, entry.get("collectedAmount")):
            payment.status = Payment.Status.FAILED
            payment.failure_reason = "Amount mismatch"
            payment.save(
                update_fields=["status", "failure_reason", "raw_provider_response", "updated_at"]
            )
            _notify_payment(payment, Payment.Status.FAILED)
            _audit_payment_event(payment, AuditLogService.Action.PAYMENT_FAILURE)
            return payment
        payment.status = Payment.Status.SUCCESSFUL
        _apply_tx_fields(payment, entry)
        payment.save(
            update_fields=[
                "status",
                "clickpesa_transaction_id",
                "network_channel",
                "raw_provider_response",
                "updated_at",
            ]
        )
        _mark_paid_if_possible(order)
        _audit_payment_event(payment, AuditLogService.Action.PAYMENT_SUCCESS)
    elif logic_status == Payment.Status.FAILED:
        payment.status = Payment.Status.FAILED
        _apply_tx_fields(payment, entry)
        payment.failure_reason = payment.failure_reason or str(gateway_message or "")
        payment.save(
            update_fields=[
                "status",
                "clickpesa_transaction_id",
                "failure_reason",
                "network_channel",
                "raw_provider_response",
                "updated_at",
            ]
        )
        _fail_order_if_possible(order)
        _audit_payment_event(payment, AuditLogService.Action.PAYMENT_FAILURE)
    else:
        payment.status = Payment.Status.PENDING
        payment.save(update_fields=["status", "raw_provider_response", "updated_at"])
    return payment
