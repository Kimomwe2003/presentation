"""Payment endpoints (Prompt 09).

- ``POST /api/payments/initiate/``          start a ClickPesa USSD-PUSH attempt
- ``POST /api/clickpesa/webhook/``           ClickPesa callback (canonical URL)
- ``POST /api/payments/webhook/clickpesa/`` ClickPesa callback (legacy alias)
- ``GET  /api/payments/<order_id>/status/`` local payment+order state (polling)
- ``POST /api/payments/<order_id>/verify/`` manual fallback querying ClickPesa
"""

import json
import logging
import re

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from orders.models import Order

from .models import Payment
from .permissions import IsOrderBuyer
from .serializers import PaymentSerializer
from .services.payment_service import (
    PaymentError,
    WebhookSignatureError,
    handle_webhook,
    initiate_payment,
    verify_payment_status,
)

logger = logging.getLogger("payments.webhook")

TZ_PHONE_RE = re.compile(r"^255\d{9}$")

# ANSI colour codes for beautiful terminal output
_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


def _banner(colour: str, title: str) -> str:
    line = "=" * 60
    return f"\n{colour}{_BOLD}{line}\n  {title}\n{line}{_RESET}"


def _payment_response(payment, order: Order) -> dict:
    return {
        "payment": PaymentSerializer(payment).data if payment else None,
        "order": {
            "id": order.id,
            "status": order.status,
            "status_label": order.get_status_display(),
        },
    }


class PaymentInitiateView(APIView):
    """POST /api/payments/initiate/  {order_id, phone_number}"""

    permission_classes = [permissions.IsAuthenticated, IsOrderBuyer]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "payment_initiate"

    def post(self, request):
        order = get_object_or_404(
            Order.objects.filter(buyer=request.user), pk=request.data.get("order_id")
        )
        phone_number = str(request.data.get("phone_number", "")).strip()
        if not TZ_PHONE_RE.fullmatch(phone_number):
            return Response(
                {
                    "detail": (
                        "Phone number must be a Tanzanian number without +, "
                        "e.g. 255712345678."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        print(
            f"{_CYAN}{_BOLD}\n[PAYMENT INITIATE]{_RESET}"
            f"  Order #{order.order_number}  Phone: {phone_number}"
        )

        try:
            payment = initiate_payment(order, phone_number)
        except PaymentError as exc:
            print(f"{_RED}[PAYMENT ERROR]{_RESET}  {exc}")
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        order.refresh_from_db()
        print(
            f"{_GREEN}[PAYMENT PENDING]{_RESET}"
            f"  Ref: {payment.external_reference}  Status: {payment.status}"
        )
        return Response(_payment_response(payment, order), status=status.HTTP_201_CREATED)


class ClickPesaWebhookView(APIView):
    """POST /api/clickpesa/webhook/ — called by ClickPesa, not the app.

    Unauthenticated by design (the gateway has no JWT); authenticity is proven
    by the payload checksum. A failed signature check returns 403 and nothing is
    processed.
    """

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else {}

        # ── Print raw incoming payload to terminal ────────────────────────────
        event = payload.get("event", "UNKNOWN")
        data = payload.get("data", {})
        ref = (
            data.get("orderReference")
            or data.get("paymentReference")
            or payload.get("orderReference")
            or "N/A"
        )
        raw_status = (
            data.get("status")
            or payload.get("status")
            or "N/A"
        )
        amount = data.get("collectedAmount") or data.get("amount") or "N/A"
        phone = data.get("phoneNumber") or data.get("msisdn") or "N/A"
        tx_id = data.get("id") or data.get("transactionId") or "N/A"
        checksum_present = bool(payload.get("checksum") or data.get("checksum"))

        print(_banner(_CYAN, "CLICKPESA WEBHOOK RECEIVED"))
        print(f"  {_BOLD}Event        :{_RESET} {event}")
        print(f"  {_BOLD}Order Ref    :{_RESET} {ref}")
        print(f"  {_BOLD}Status       :{_RESET} {raw_status}")
        print(f"  {_BOLD}Amount       :{_RESET} {amount} TZS")
        print(f"  {_BOLD}Phone        :{_RESET} {phone}")
        print(f"  {_BOLD}Transaction  :{_RESET} {tx_id}")
        print(f"  {_BOLD}Checksum OK  :{_RESET} {'yes' if checksum_present else 'NOT PRESENT'}")
        print(f"  {_BOLD}Full Payload :{_RESET}")
        print(json.dumps(payload, indent=4))

        try:
            handle_webhook(payload)
        except WebhookSignatureError as exc:
            print(_banner(_RED, "WEBHOOK REJECTED — INVALID CHECKSUM"))
            print(f"  Reason: {exc}")
            logger.warning("ClickPesa webhook rejected: %s | payload=%s", exc, payload)
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        # ── Determine outcome and print result ────────────────────────────────
        upper_event = str(event).strip().replace("_", " ").upper()
        is_success = (
            "RECEIVED" in upper_event
            or raw_status.upper() in ("SUCCESS", "SUCCESSFUL", "COMPLETED")
        )
        if is_success:
            print(_banner(_GREEN, f"✓ PAYMENT SUCCESSFUL — Order {ref}"))
            print(f"  Amount collected: {amount} TZS")
            print(f"  Transaction ID  : {tx_id}")
            print("  Order status    : PAID")
            logger.info(
                "ClickPesa payment SUCCESS | ref=%s tx=%s amount=%s",
                ref, tx_id, amount,
            )
        elif "FAILED" in upper_event or "CANCELLED" in upper_event:
            print(_banner(_RED, f"✗ PAYMENT FAILED — Order {ref}"))
            print(f"  Status  : {raw_status}")
            print(f"  Message : {data.get('message', 'N/A')}")
            logger.warning(
                "ClickPesa payment FAILED | ref=%s status=%s msg=%s",
                ref, raw_status, data.get("message"),
            )
        else:
            print(_banner(_YELLOW, f"? WEBHOOK RECEIVED (unresolved) — {event}"))

        return Response({"status": "ok"})


class PaymentStatusView(APIView):
    """GET /api/payments/<order_id>/status/ — local state for polling."""

    permission_classes = [permissions.IsAuthenticated, IsOrderBuyer]

    def get(self, request, order_id: int):
        order = get_object_or_404(Order.objects.filter(buyer=request.user), pk=order_id)
        payment = Payment.objects.filter(order=order).order_by("-created_at").first()
        return Response(_payment_response(payment, order))


class PaymentVerifyView(APIView):
    """POST /api/payments/<order_id>/verify/ — manual fallback."""

    permission_classes = [permissions.IsAuthenticated, IsOrderBuyer]

    def post(self, request, order_id: int):
        order = get_object_or_404(Order.objects.filter(buyer=request.user), pk=order_id)
        try:
            payment = verify_payment_status(order)
        except PaymentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        order.refresh_from_db()

        status_label = payment.status.upper()
        if payment.status == Payment.Status.SUCCESSFUL:
            print(_banner(_GREEN, f"✓ VERIFY CONFIRMED SUCCESSFUL — Order #{order.order_number}"))
        elif payment.status == Payment.Status.FAILED:
            print(_banner(_RED, f"✗ VERIFY CONFIRMED FAILED — Order #{order.order_number}"))
        else:
            print(f"{_YELLOW}[VERIFY] Status: {status_label}{_RESET}")

        return Response(_payment_response(payment, order))
