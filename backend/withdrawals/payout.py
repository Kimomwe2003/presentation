"""ClickPesa payout integration for withdrawal completions.

When an admin moves a withdrawal to COMPLETED, we attempt to push the money to
the seller's mobile-money number via ClickPesa's disbursement API
(POST /payouts/create-mobile-money-payout). The gateway result is recorded on
the :class:`withdrawals.models.WithdrawalRequest` (``payout_reference`` /
``payout_status`` / ``payout_message``).

Design notes
------------
- This layer NEVER moves wallet money itself — that stays in
  :mod:`withdrawals.services` (the ledger is the source of truth). It only
  *instructs the gateway* and records the outcome.
- It is best-effort but explicit: every outcome is written to the request so an
  admin can see exactly what happened.
- **Demo fallback** — ClickPesa's PAYOUT API must be enabled per merchant, and
  the merchant needs real balance. When the gateway is unavailable (not
  provisioned, insufficient balance, network error, bad phone) we record the
  outcome as ``UNAVAILABLE`` with a message and let the existing completion
  flow proceed, so the app never hard-crashes a payout during a demo.
"""

import logging

from django.conf import settings

from payments.services.clickpesa_service import ClickPesaError, ClickPesaService

from .models import WithdrawalRequest

logger = logging.getLogger("withdrawals.payout")

#: Canonical ClickPesa payout statuses we care about.
_PAYOUT_SUCCESS = {"SUCCESS", "AUTHORIZED", "COMPLETED", "PENDING", "PROCESSING"}


def normalize_phone_number(value: str) -> str:
    """Convert a local mobile number to ClickPesa's country-code format.

    ClickPesa wants the number to start with the country code and no ``+``,
    e.g. ``0712345678`` -> ``255712345678`` (Tanzania).
    """
    digits = "".join(ch for ch in value if ch.isdigit())
    if digits.startswith("+"):
        digits = digits[1:]
    if digits.startswith("0"):
        digits = "255" + digits[1:]
    elif not digits.startswith("255"):
        digits = "255" + digits
    return digits


def _extract_payout(data) -> dict:
    """Best-effort pull of the payout object from a ClickPesa reply."""
    if isinstance(data, list):
        return data[0] if data and isinstance(data[0], dict) else {}
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, dict):
            return inner
        if isinstance(inner, list) and inner and isinstance(inner[0], dict):
            return inner[0]
        return data
    return {}


class WithdrawalPayoutService:
    """Records the outcome of a ClickPesa disbursement on a withdrawal."""

    @staticmethod
    def record(request: WithdrawalRequest, *, reference="", status="", message=""):
        """Persist payout fields onto the request (never raises)."""
        fields = {
            "payout_reference": reference[:64],
            "payout_status": status[:32],
            "payout_message": message,
        }
        try:
            WithdrawalRequest.objects.filter(pk=request.pk).update(**fields)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to record payout result for withdrawal %s", request.reference)

    @staticmethod
    def attempt(request: WithdrawalRequest) -> bool:
        """Call ClickPesa to disburse the withdrawal amount.

        Returns ``True`` when the gateway accepted the payout (AUTHORIZED /
        SUCCESS / PENDING), ``False`` when it could not be used. The outcome is
        always recorded on the request.
        """
        if not getattr(settings, "CLICKPESA_PAYOUTS_ENABLED", False):
            WithdrawalPayoutService.record(
                request,
                status="UNAVAILABLE",
                message="Automatic ClickPesa payouts are disabled.",
            )
            return False

        if not getattr(settings, "CLICKPESA_CLIENT_ID", "") or not getattr(
            settings, "CLICKPESA_API_KEY", ""
        ):
            WithdrawalPayoutService.record(
                request,
                status="UNAVAILABLE",
                message="ClickPesa credentials not configured on the server.",
            )
            return False

        phone = normalize_phone_number(request.mobile_money_number)
        service = ClickPesaService()
        try:
            data = service.disburse(
                amount=str(request.amount),
                order_reference=request.reference,
                phone_number=phone,
            )
        except ClickPesaError as exc:
            detail = _error_detail(exc)
            logger.warning(
                "ClickPesa payout failed for %s: %s", request.reference, detail
            )
            WithdrawalPayoutService.record(
                request,
                status="UNAVAILABLE",
                message=detail,
            )
            return False

        payout = _extract_payout(data)
        gateway_status = str(
            payout.get("status") or (data.get("status") if isinstance(data, dict) else "") or ""
        ).upper()
        payout_id = str(
            payout.get("id") or (data.get("id") if isinstance(data, dict) else "") or ""
        )

        if gateway_status in _PAYOUT_SUCCESS:
            WithdrawalPayoutService.record(
                request,
                reference=payout_id,
                status=gateway_status or "AUTHORIZED",
                message="Payout sent via ClickPesa.",
            )
            return True

        message = str(data) if not isinstance(data, dict) else str(
            payout.get("message") or data.get("message") or "Unexpected payout response."
        )
        WithdrawalPayoutService.record(
            request,
            reference=payout_id,
            status=gateway_status or "UNAVAILABLE",
            message=message,
        )
        return gateway_status in {"PENDING", "PROCESSING"}


def _error_detail(exc: ClickPesaError) -> str:
    """Human-readable one-liner from a ClickPesaError."""
    resp = exc.response
    if isinstance(resp, dict):
        msg = resp.get("message") or resp.get("error") or resp.get("detail")
        if msg:
            return str(msg)
        return str(resp)
    if isinstance(resp, str) and resp.strip():
        return resp.strip()
    return str(exc) or "ClickPesa payout unavailable."
