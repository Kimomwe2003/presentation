"""Raw ClickPesa HTTP client.

This module only makes the API calls documented in docs/CLICKPESA_INTEGRATION.md:
authenticate (generate-token), initiate USSD-PUSH, and query payment status. It
contains **no business logic** — deciding what a result means and moving orders
forward is PaymentService's job.

Credentials come exclusively from environment variables (django.conf.settings)
and are never returned to or readable by the mobile app.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

from ..checksum import create_payload_checksum

TOKEN_TTL_SECONDS = 60 * 60  # ClickPesa JWTs are valid for 1 hour.

# ── Canonical payment-status normalization ────────────────────────────────
# ClickPesa reports success/failure in several spellings depending on the
# endpoint/event ("SUCCESS", "PAYMENT SUCCESSFUL", "COMPLETED", ...).  These
# sets fold them all onto one canonical attempt status (mirrors the FastAPI
# reference implementation in zanelimu_platform).
_PAYMENT_STATUS_COMPLETED = {
    "SUCCESS", "SUCCESSFUL", "PAYMENT SUCCESSFUL", "PAYMENT RECEIVED",
    "COMPLETED", "PAYMENT COMPLETED", "PAID", "SETTLED", "SETTLED/PAID",
    "PAYMENT SETTLED",
}
_PAYMENT_STATUS_FAILED = {
    "FAILED", "PAYMENT FAILED", "DECLINED", "PAYMENT DECLINED", "EXPIRED",
    "INSUFFICIENT FUNDS", "FAILED/INSUFFICIENT FUNDS", "REJECTED", "REVERSED",
    "UNPAID", "ERROR", "NOT SUCCESSFUL",
}
_PAYMENT_STATUS_CANCELLED = {
    "CANCELLED", "PAYMENT CANCELLED", "CANCELLED BY USER",
    "CANCELLED BY CUSTOMER", "ABORTED",
}
_PAYMENT_STATUS_PENDING = {
    "PENDING", "INITIATED", "PROCESSING", "IN PROGRESS", "STARTED",
    "PAYMENT PENDING", "USSD SENT", "PUSH SENT", "WAITING",
    "AWAITING CONFIRMATION", "CREATED", "OPEN", "PENDING CONFIRMATION", "PROCESS",
}

# Substrings in a status reply that mean "the gateway has no record of this
# reference".
_NOT_FOUND_MARKERS = ("invalid or missing payment", "not found", "does not exist")


class ClickPesaError(Exception):
    """Raised when a ClickPesa call fails (transport, HTTP, or bad payload)."""

    def __init__(self, message: str, status_code: int | None = None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


def normalize_payment_status(status_raw) -> str | None:
    """Map any ClickPesa status spelling onto a canonical attempt status.

    Returns one of ``completed`` | ``failed`` | ``cancelled`` | ``pending``,
    or ``None`` when the status is unrecognised.
    """
    if status_raw is None:
        return None
    s = str(status_raw).strip().upper().replace("_", " ")
    if not s:
        return None
    if s in _PAYMENT_STATUS_COMPLETED:
        return "completed"
    if s in _PAYMENT_STATUS_FAILED:
        return "failed"
    if s in _PAYMENT_STATUS_CANCELLED:
        return "cancelled"
    if s in _PAYMENT_STATUS_PENDING:
        return "pending"
    return None


def _unwrap_status_payload(data) -> dict | None:
    """Best-effort extraction of the primary payment object from a reply.

    ClickPesa's status endpoint returns a JSON *array* of payment records
    (``[{...}]``) but some wrappers nest the record under a ``data`` key that
    may itself be a list.
    """
    if isinstance(data, list):
        return data[0] if data and isinstance(data[0], dict) else None
    if not isinstance(data, dict):
        return None
    inner = data.get("data")
    if isinstance(inner, list):
        return inner[0] if inner and isinstance(inner[0], dict) else None
    if isinstance(inner, dict):
        return inner
    return data


def parse_payment_status_response(data) -> tuple[str | None, str | None]:
    """Parse a ClickPesa status reply into ``(canonical_status, message)``.

    ``canonical_status`` is one of ``completed|failed|cancelled|pending``, or
    ``None`` when the reply is not a payment status at all (no gateway record,
    or the request hit a catch-all health payload).
    """
    if isinstance(data, list) and not data:
        return None, None
    if not isinstance(data, dict) and not isinstance(data, list):
        return None, None
    text = json.dumps(data).lower()
    if any(m in text for m in _NOT_FOUND_MARKERS):
        return None, None

    primary = _unwrap_status_payload(data)
    if primary is None:
        return None, None
    if primary.get("name") == "clickpesa-core":
        return None, None

    status = None
    for source in (data, primary):
        if not isinstance(source, dict):
            continue
        for key in ("status", "paymentStatus", "transactionStatus"):
            val = source.get(key)
            if isinstance(val, str) and val.strip():
                status = val
                break
        if status:
            break

    canonical = normalize_payment_status(status)
    message = None
    for source in (data, primary):
        if not isinstance(source, dict):
            continue
        val = source.get("message")
        if isinstance(val, str) and val.strip():
            message = val
            break
    return canonical, message


def extract_transaction_id(data) -> str | None:
    """Best-effort extraction of ClickPesa's transaction id from a reply."""
    primary = _unwrap_status_payload(data)
    for source in (data, primary):
        if not isinstance(source, dict):
            continue
        for key in ("id", "transactionId", "transactionReference", "paymentReference"):
            val = source.get(key)
            if isinstance(val, str) and val.strip():
                return val
    return None


class ClickPesaService:
    def __init__(
        self,
        base_url: str | None = None,
        client_id: str | None = None,
        api_key: str | None = None,
        webhook_secret: str | None = None,
        checksum_secret: str | None = None,
        timeout: int | None = None,
    ):
        self.timeout = timeout if timeout is not None else getattr(settings, "CLICKPESA_TIMEOUT", 15)
        self.base_url = (base_url or settings.CLICKPESA_BASE_URL).rstrip("/")
        self.client_id = client_id or settings.CLICKPESA_CLIENT_ID
        self.api_key = api_key or settings.CLICKPESA_API_KEY
        # webhook_secret: used to VERIFY inbound webhook payloads from ClickPesa
        self.webhook_secret = (
            webhook_secret if webhook_secret is not None else settings.CLICKPESA_WEBHOOK_SECRET
        )
        # checksum_secret: used to SIGN outbound USSD-push request payloads
        # This is the CHK... key from the ClickPesa dashboard (separate from API Key)
        self.checksum_secret = (
            checksum_secret if checksum_secret is not None
            else getattr(settings, "CLICKPESA_CHECKSUM_SECRET", self.webhook_secret)
        )
        self._token: str | None = None
        self._token_acquired_at: float = 0.0

    # -- Public API ---------------------------------------------------------

    def authenticate(self) -> str:
        """POST /generate-token -> "Bearer <jwt>". Cached for one hour."""
        if self._token and time.monotonic() - self._token_acquired_at < TOKEN_TTL_SECONDS:
            return self._token
        if not self.client_id or not self.api_key:
            raise ClickPesaError(
                "ClickPesa client credentials are not configured on the server."
            )
        import logging
        log = logging.getLogger("payments.clickpesa")
        log.debug(
            "ClickPesa authenticate | base_url=%s client_id=%s...",
            self.base_url, self.client_id[:8] if self.client_id else "NONE",
        )
        response = self._request(
            "POST",
            "/generate-token",
            json_body=None,
            headers={"client-id": self.client_id, "api-key": self.api_key},
            authenticated=False,
        )
        token = response.get("token") if isinstance(response, dict) else None
        if not token:
            log.error("ClickPesa auth failed — no token in response: %s", response)
            raise ClickPesaError("ClickPesa did not return an access token.", response=response)
        log.debug("ClickPesa auth OK | token=%s...", str(token)[:20])
        self._token = str(token)
        self._token_acquired_at = time.monotonic()
        return self._token

    def initiate_ussd_push(
        self, amount: str, order_reference: str, phone_number: str, webhook_url: str | None = None
    ) -> dict:
        """POST /payments/initiate-ussd-push-request. Returns the raw response dict."""
        import logging
        log = logging.getLogger("payments.clickpesa")
        payload = {
            "amount": amount,
            "orderReference": order_reference,
            "phoneNumber": phone_number,
            "currency": settings.CLICKPESA_CURRENCY,
        }
        if webhook_url:
            payload["webhookUrl"] = webhook_url
        log_payload = {k: v for k, v in payload.items() if k != "checksum"}
        log.debug("ClickPesa USSD push | payload=%s", log_payload)
        return self._request(
            "POST", "/payments/initiate-ussd-push-request", json_body=payload, sign=True
        )

    def preview_ussd_push(
        self, amount: str, order_reference: str, phone_number: str | None = None,
    ) -> dict:
        """POST /payments/preview-ussd-push-request.

        Validates the payment details and returns available payment methods
        without actually sending the USSD push. Useful for checking if a
        phone number / network is supported before initiating payment.
        """
        payload: dict = {
            "amount": amount,
            "orderReference": order_reference,
            "currency": settings.CLICKPESA_CURRENCY,
        }
        if phone_number:
            payload["phoneNumber"] = phone_number
        return self._request(
            "POST", "/payments/preview-ussd-push-request", json_body=payload, sign=True
        )

    def query_payment_status(self, order_reference: str) -> list:
        """GET /payments/{orderReference}. Returns a list of payment objects."""
        path = f"/payments/{urllib.parse.quote(order_reference)}"
        return self._request("GET", path)

    def disburse(
        self, amount: str, order_reference: str, phone_number: str
    ) -> dict:
        """POST /payouts/create-mobile-money-payout (send money to a wallet).

        ``phone_number`` must start with the country code WITHOUT the plus sign
        (e.g. ``255712345678``). The amount is deducted from the merchant's
        ClickPesa balance.

        Requires the PAYOUT API feature to be enabled on the application
        (ClickPesa returns "Application has no access to PAYOUT API feature"
        otherwise). Raises :class:`ClickPesaError` on transport/HTTP failure.
        """
        import logging

        log = logging.getLogger("payments.clickpesa")
        payload = {
            "amount": amount,
            "orderReference": order_reference,
            "phoneNumber": phone_number,
            "currency": settings.CLICKPESA_CURRENCY,
        }
        log.debug("ClickPesa payout | reference=%s amount=%s", order_reference, amount)
        return self._request(
            "POST", "/payouts/create-mobile-money-payout", json_body=payload, sign=True
        )

    def query_payout_status(self, order_reference: str) -> list:
        """GET /payouts/{orderReference}. Returns a list of payout objects."""
        path = f"/payouts/{urllib.parse.quote(order_reference)}"
        return self._request("GET", path)

    # -- Internals ----------------------------------------------------------

    def _get_token(self) -> str:
        if not self._token:
            self.authenticate()
        assert self._token is not None
        return self._token

    def _request(
        self,
        method,
        path,
        *,
        json_body=None,
        headers=None,
        authenticated=True,
        sign=False,
    ):
        """Perform a JSON request; raise ClickPesaError on transport/HTTP failure."""
        url = self.base_url + path
        headers = dict(headers or {})
        # Use checksum_secret (CHK...) to sign outbound payloads sent to ClickPesa
        signing_key = self.checksum_secret or self.webhook_secret
        if sign and signing_key:
            json_body = dict(json_body or {})
            json_body["checksum"] = create_payload_checksum(signing_key, json_body)

        if authenticated:
            headers["Authorization"] = self._get_token()

        body = None
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")

        try:
            return self._open(url, method, headers, body)
        except ClickPesaError as exc:
            # Token may have expired mid-flight — refresh exactly once and retry.
            if authenticated and exc.status_code == 401 and self._token:
                self._token = None
                self._token_acquired_at = 0.0
                headers["Authorization"] = self._get_token()
                return self._open(url, method, headers, body)
            raise

    def _open(self, url, method, headers, body):
        request = urllib.request.Request(url, data=body, method=method, headers=headers)
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            try:
                parsed = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = raw
            raise ClickPesaError(
                f"ClickPesa responded with HTTP {exc.code}.", status_code=exc.code, response=parsed
            ) from exc
        except urllib.error.URLError as exc:
            raise ClickPesaError(f"Could not reach ClickPesa: {exc.reason}") from exc
