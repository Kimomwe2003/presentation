"""ClickPesa payment flow tests (Prompt 09).

Covers: initiation (ownership, phone validation, retry), webhook checksum
verification, idempotency (duplicate callbacks), amount mismatch, failure →
PAYMENT_FAILED + retry, manual verify reflecting true remote state, and the rule
that an order only reaches PAID through a verified payment event.
"""

from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.test_api import auth, make_category, make_product, make_user
from orders.models import Order
from payments.checksum import create_payload_checksum
from payments.models import Payment
from payments.services.clickpesa_service import ClickPesaError, ClickPesaService

INITIATE_URL = "/api/payments/initiate/"
WEBHOOK_URL = "/api/payments/webhook/clickpesa/"
SECRET = "test-webhook-secret"


def signed(payload: dict) -> dict:
    """Attach a valid checksum to a webhook payload (excludes checksum fields)."""
    body = {k: v for k, v in payload.items() if k not in ("checksum", "checksumMethod")}
    payload["checksum"] = create_payload_checksum(SECRET, body)
    return payload


@override_settings(CLICKPESA_WEBHOOK_SECRET=SECRET)
class PaymentFlowBase(APITestCase):
    def setUp(self):
        self.buyer = make_user("buyer@example.com")
        self.other = make_user("other@example.com")
        self.seller = make_user("seller@example.com")
        self.category = make_category()
        self.product = make_product(self.seller, self.category, price=Decimal("50.00"))
        auth(self.client, self.buyer)
        self.order = self._create_order()

    def _create_order(self) -> Order:
        self.client.post(
            "/api/cart/items/", {"product_id": self.product.pk, "quantity": 1}, format="json"
        )
        response = self.client.post("/api/orders/", {"payment_method": "card"}, format="json")
        return Order.objects.get(pk=response.data["id"])

    def _initiate(self, phone: str = "255712345678", remote_status: str = "PROCESSING"):
        with patch.object(
            ClickPesaService,
            "initiate_ussd_push",
            return_value={"status": remote_status, "id": "TXN123", "orderReference": "x"},
        ):
            response = self.client.post(
                INITIATE_URL,
                {"order_id": self.order.pk, "phone_number": phone},
                format="json",
            )
        return response

    def _payment(self) -> Payment:
        return Payment.objects.filter(order=self.order).order_by("-created_at").first()

    def _webhook(self, event: str, remote_status: str, *, reference: str, collected_amount="50"):
        payload = signed(
            {
                "event": event,
                "data": {
                    "id": "CP123",
                    "status": remote_status,
                    "orderReference": reference,
                    "collectedAmount": collected_amount,
                    "collectedCurrency": "TZS",
                    "message": "ok",
                    "channel": "TIGO-PESA",
                },
            }
        )
        return self.client.post(WEBHOOK_URL, payload, format="json")


class PaymentInitiateTests(PaymentFlowBase):
    def test_initiate_requires_auth(self):
        self.client.credentials()
        response = self.client.post(
            INITIATE_URL, {"order_id": 1, "phone_number": "x"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_initiate_requires_valid_phone(self):
        response = self.client.post(
            INITIATE_URL, {"order_id": self.order.pk, "phone_number": "0712345678"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Payment.objects.filter(order=self.order).exists())

    def test_initiate_scoped_to_buyer(self):
        auth(self.client, self.other)
        response = self.client.post(
            INITIATE_URL, {"order_id": self.order.pk, "phone_number": "255712345678"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_initiate_creates_pending_payment(self):
        response = self._initiate(remote_status="PROCESSING")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment = self._payment()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.amount, self.order.total)
        self.assertTrue(payment.external_reference.startswith("RH"))
        self.assertEqual(response.data["order"]["status"], Order.Status.PENDING_PAYMENT)

    def test_initiate_alone_never_pays(self):
        # A PROCESSING start must not move the order — only a verified event may.
        self._initiate(remote_status="PROCESSING")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)

    def test_initiate_immediate_provider_success_pays(self):
        response = self._initiate(remote_status="SUCCESS")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.order.refresh_from_db()
        self.assertEqual(response.data["payment"]["status"], Payment.Status.SUCCESSFUL)
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_initiate_rejects_unpayable_order(self):
        auth(self.client, self.buyer)
        self.client.post(f"/api/orders/{self.order.pk}/cancel/", {}, format="json")
        response = self.client.post(
            INITIATE_URL, {"order_id": self.order.pk, "phone_number": "255712345678"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_initiate_failure_marks_attempt_failed(self):
        with patch.object(
            ClickPesaService,
            "initiate_ussd_push",
            side_effect=ClickPesaError("network down"),
        ):
            response = self.client.post(
                INITIATE_URL,
                {"order_id": self.order.pk, "phone_number": "255712345678"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        payment = self._payment()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)


class PaymentWebhookTests(PaymentFlowBase):
    def test_webhook_rejects_unsigned(self):
        self._initiate()
        payload = {
            "event": "PAYMENT RECEIVED",
            "data": {"orderReference": self._payment().external_reference, "status": "SUCCESS"},
        }
        response = self.client.post(WEBHOOK_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_webhook_rejects_bad_checksum(self):
        self._initiate()
        payload = signed(
            {
                "event": "PAYMENT RECEIVED",
                "data": {"orderReference": self._payment().external_reference, "status": "SUCCESS"},
            }
        )
        payload["checksum"] = "deadbeef"
        response = self.client.post(WEBHOOK_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_successful_callback_transitions_order(self):
        self._initiate()
        response = self._webhook(
            "PAYMENT RECEIVED", "SUCCESS", reference=self._payment().external_reference
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self._payment().refresh_from_db()
        self.assertEqual(self._payment().status, Payment.Status.SUCCESSFUL)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_duplicate_callback_is_noop(self):
        self._initiate()
        reference = self._payment().external_reference
        first = self._webhook("PAYMENT RECEIVED", "SUCCESS", reference=reference)
        second = self._webhook("PAYMENT RECEIVED", "SUCCESS", reference=reference)
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(Payment.objects.filter(order=self.order).count(), 1)
        self._payment().refresh_from_db()
        self.assertEqual(self._payment().status, Payment.Status.SUCCESSFUL)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_failed_callback_marks_order_payment_failed(self):
        self._initiate()
        response = self._webhook(
            "PAYMENT FAILED", "FAILED", reference=self._payment().external_reference
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._payment().status, Payment.Status.FAILED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAYMENT_FAILED)

    def test_unknown_reference_acknowledged_without_processing(self):
        response = self._webhook("PAYMENT RECEIVED", "SUCCESS", reference="RH-UNKNOWN-1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Payment.objects.count(), 0)

    def test_amount_mismatch_blocks_transition(self):
        self._initiate()
        response = self._webhook(
            "PAYMENT RECEIVED",
            "SUCCESS",
            reference=self._payment().external_reference,
            collected_amount="10",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._payment().status, Payment.Status.FAILED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)

    def test_unrelated_event_ignored(self):
        self._initiate()
        reference = self._payment().external_reference
        payload = signed(
            {
                "event": "PAYOUT INITIATED",
                "data": {"orderReference": reference, "status": "SUCCESS"},
            }
        )
        response = self.client.post(WEBHOOK_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._payment().status, Payment.Status.PENDING)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)

    def test_cancelled_callback_marks_order_payment_failed(self):
        self._initiate()
        response = self._webhook(
            "PAYMENT CANCELLED", "CANCELLED", reference=self._payment().external_reference
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._payment().status, Payment.Status.FAILED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAYMENT_FAILED)

    def test_event_name_underscore_normalised(self):
        # ClickPesa may deliver "PAYMENT_RECEIVED" instead of "PAYMENT RECEIVED".
        self._initiate()
        reference = self._payment().external_reference
        payload = signed(
            {
                "event": "PAYMENT_RECEIVED",
                "data": {
                    "id": "TX-U1",
                    "status": "SUCCESS",
                    "orderReference": reference,
                    "collectedAmount": "50",
                },
            }
        )
        response = self.client.post(WEBHOOK_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._payment().status, Payment.Status.SUCCESSFUL)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_successful_callback_stores_transaction_id(self):
        self._initiate()
        payment = self._payment()
        # Initiate's mock populates a gateway id; simulate a case where the
        # attempt carried no transaction id until the webhook supplies one.
        payment.clickpesa_transaction_id = ""
        payment.save(update_fields=["clickpesa_transaction_id"])
        payload = signed(
            {
                "event": "PAYMENT RECEIVED",
                "data": {
                    "id": "CP-TX-STORED",
                    "status": "SUCCESS",
                    "orderReference": payment.external_reference,
                    "collectedAmount": "50",
                },
            }
        )
        response = self.client.post(WEBHOOK_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._payment().clickpesa_transaction_id, "CP-TX-STORED")

    def test_failed_callback_stores_failure_reason(self):
        self._initiate()
        payment = self._payment()
        payment.clickpesa_transaction_id = ""
        payment.save(update_fields=["clickpesa_transaction_id"])
        payload = signed(
            {
                "event": "PAYMENT FAILED",
                "data": {
                    "id": "CP-TX-3",
                    "status": "FAILED",
                    "orderReference": payment.external_reference,
                    "message": "Insufficient funds",
                },
            }
        )
        response = self.client.post(WEBHOOK_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment = self._payment()
        self.assertEqual(payment.clickpesa_transaction_id, "CP-TX-3")
        self.assertEqual(payment.failure_reason, "Insufficient funds")

    def test_callback_resolved_by_transaction_id(self):
        # A webhook that arrives without our orderReference but carrying the
        # stored gateway transaction id must resolve the right payment.
        self._initiate()
        payment = self._payment()
        payment.clickpesa_transaction_id = "CP-CORRELATE-1"
        payment.save(update_fields=["clickpesa_transaction_id"])
        payload = signed(
            {
                "event": "PAYMENT RECEIVED",
                "data": {
                    "id": "CP-CORRELATE-1",
                    "status": "SUCCESS",
                    "collectedAmount": "50",
                },
            }
        )
        response = self.client.post(WEBHOOK_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESSFUL)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_successful_webhook_creates_notification(self):
        self._initiate()
        response = self._webhook(
            "PAYMENT RECEIVED", "SUCCESS", reference=self._payment().external_reference
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        from notifications.models import Notification

        note = Notification.objects.filter(
            user=self.buyer, type=Notification.Type.PAYMENT_RESULT
        ).first()
        self.assertIsNotNone(note)
        self.assertIn("paid", note.title.lower())


class PaymentRetryTests(PaymentFlowBase):
    def test_failure_then_retry_creates_new_attempt(self):
        self._initiate()
        first_ref = self._payment().external_reference
        self._webhook("PAYMENT FAILED", "FAILED", reference=first_ref)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAYMENT_FAILED)

        response = self._initiate(remote_status="PROCESSING")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)

        first = Payment.objects.get(external_reference=first_ref)
        self.assertEqual(first.status, Payment.Status.FAILED)  # history kept, not expired
        second = self._payment()
        self.assertNotEqual(second.pk, first.pk)
        self.assertNotEqual(second.external_reference, first_ref)
        self.assertEqual(second.status, Payment.Status.PENDING)

    def test_new_attempt_expires_previous_pending(self):
        # Initiating while the order is still PENDING_PAYMENT expires the older
        # PENDING attempt (it is superseded) rather than leaving two live ones.
        self._initiate(remote_status="PROCESSING")
        first_ref = self._payment().external_reference
        response = self._initiate(remote_status="PROCESSING")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        first = Payment.objects.get(external_reference=first_ref)
        self.assertEqual(first.status, Payment.Status.EXPIRED)
        self.assertEqual(self._payment().status, Payment.Status.PENDING)
        self.assertEqual(
            Payment.objects.filter(order=self.order, status=Payment.Status.PENDING).count(), 1
        )
    def test_retry_flow_to_success(self):
        self._initiate()
        first_ref = self._payment().external_reference
        self._webhook("PAYMENT FAILED", "FAILED", reference=first_ref)
        self._initiate(remote_status="PROCESSING")
        second = self._payment()
        response = self._webhook("PAYMENT RECEIVED", "SUCCESS", reference=second.external_reference)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._payment().status, Payment.Status.SUCCESSFUL)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)


class PaymentVerifyTests(PaymentFlowBase):
    def test_verify_reflects_remote_success(self):
        self._initiate(remote_status="PROCESSING")
        self.assertIsNotNone(self._payment())
        with patch.object(
            ClickPesaService,
            "query_payment_status",
            return_value=[
                {
                    "status": "SUCCESS",
                    "orderReference": self._payment().external_reference,
                    "collectedAmount": "50",
                }
            ],
        ):
            response = self.client.post(f"/api/payments/{self.order.pk}/verify/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["payment"]["status"], Payment.Status.SUCCESSFUL)
        self.assertEqual(response.data["order"]["status"], Order.Status.PAID)

    def test_verify_reflects_remote_failure(self):
        self._initiate(remote_status="PROCESSING")
        with patch.object(
            ClickPesaService,
            "query_payment_status",
            return_value=[
                {"status": "FAILED", "orderReference": self._payment().external_reference}
            ],
        ):
            response = self.client.post(f"/api/payments/{self.order.pk}/verify/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["payment"]["status"], Payment.Status.FAILED)
        self.assertEqual(response.data["order"]["status"], Order.Status.PAYMENT_FAILED)

    def test_verify_keeps_pending_when_remote_processing(self):
        self._initiate(remote_status="PROCESSING")
        with patch.object(
            ClickPesaService,
            "query_payment_status",
            return_value=[
                {"status": "PROCESSING", "orderReference": self._payment().external_reference}
            ],
        ):
            response = self.client.post(f"/api/payments/{self.order.pk}/verify/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["payment"]["status"], Payment.Status.PENDING)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)

    def test_verify_requires_existing_attempt(self):
        response = self.client.post(f"/api/payments/{self.order.pk}/verify/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_scoped_to_buyer(self):
        self._initiate()
        auth(self.client, self.other)
        response = self.client.post(f"/api/payments/{self.order.pk}/verify/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PaymentReconcileTests(PaymentFlowBase):
    def _stale_pending(self) -> Payment:
        """Create a payment attempt and age it past the reconciliation window."""
        self._initiate(remote_status="PROCESSING")
        payment = self._payment()
        payment.created_at = payment.created_at - timezone.timedelta(minutes=10)
        payment.status = Payment.Status.PENDING
        payment.save(update_fields=["created_at", "status"])
        return payment

    def test_reconcile_applies_remote_success(self):
        self._stale_pending()
        with patch.object(
            ClickPesaService,
            "query_payment_status",
            return_value=[{"status": "SUCCESS", "collectedAmount": "50"}],
        ):
            call_command("reconcile_payments", window_minutes=1)
        self._payment().refresh_from_db()
        self.assertEqual(self._payment().status, Payment.Status.SUCCESSFUL)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_reconcile_applies_remote_failure(self):
        self._stale_pending()
        with patch.object(
            ClickPesaService,
            "query_payment_status",
            return_value=[{"status": "FAILED", "message": "Insufficient funds"}],
        ):
            call_command("reconcile_payments", window_minutes=1)
        payment = self._payment()
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(payment.failure_reason, "Insufficient funds")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAYMENT_FAILED)

    def test_reconcile_keeps_pending_when_gateway_processing(self):
        self._stale_pending()
        with patch.object(
            ClickPesaService,
            "query_payment_status",
            return_value=[{"status": "PROCESSING"}],
        ):
            call_command("reconcile_payments", window_minutes=1)
        self._payment().refresh_from_db()
        self.assertEqual(self._payment().status, Payment.Status.PENDING)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)


class PaymentStatusEndpointTests(PaymentFlowBase):
    def test_status_returns_local_state(self):
        self._initiate()
        response = self.client.get(f"/api/payments/{self.order.pk}/status/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["payment"]["status"], Payment.Status.PENDING)
        self.assertEqual(response.data["order"]["status"], Order.Status.PENDING_PAYMENT)

    def test_status_scoped_to_buyer(self):
        self._initiate()
        auth(self.client, self.other)
        response = self.client.get(f"/api/payments/{self.order.pk}/status/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_status_without_attempt(self):
        response = self.client.get(f"/api/payments/{self.order.pk}/status/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["payment"])
