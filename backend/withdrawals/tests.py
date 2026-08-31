"""Withdrawal tests (Prompt 12).

Covers:
- request creation reserves the amount via a hard-debit WITHDRAWAL ledger row
- minimum-amount and insufficient-balance guards (service and DB level)
- rejection of float money inputs
- admin-only transitions (process/complete/fail/reject) with a state machine
- atomic reversal: FAILED/REJECTED writes an exact REFUND row
- idempotent transitions: a terminal request cannot be moved again
- concurrency: two admins acting on the same request cannot double-move it
- API: create/list, per-user isolation, admin queue, and staff-gated actions
"""

import threading
from decimal import Decimal

from django.db import close_old_connections
from django.test import TransactionTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.test_api import auth
from wallet.models import LedgerTransaction, Wallet
from wallet.services import WalletService
from withdrawals.models import WithdrawalRequest
from withdrawals.services import InsufficientBalance, WithdrawalService

WITHDRAWALS_URL = "/api/withdrawals/"

_counter = 0


def _unique_email(prefix: str) -> str:
    global _counter
    _counter += 1
    local, domain = (f"{prefix}@example.com").split("@", 1)
    return f"{local}-{_counter}@{domain}"


def make_user(prefix: str = "seller"):
    from catalog.test_api import make_user as _backend_make_user

    return _backend_make_user(email=_unique_email(prefix))


def make_admin(prefix: str = "admin"):
    user = make_user(prefix)
    user.is_staff = True
    user.save()
    return user


def wallet_balance(user) -> Decimal:
    """Fresh balance read — avoids the cached reverse ``user.wallet``."""
    return Wallet.objects.get(user=user).balance


class WithdrawalFixtures:
    def fund_wallet(self, user, amount: str = "100000.00") -> None:
        WalletService.credit(
            user,
            Decimal(amount),
            reference="test-seed",
            description="Test credit",
        )

    def create_request(self, user, amount: str = "20000.00") -> WithdrawalRequest:
        return WithdrawalService.request_withdrawal(
            user,
            amount=Decimal(amount),
            provider=WithdrawalRequest.Provider.MPESA,
            mobile_money_number="255712345678",
        )


class WithdrawalServiceTests(APITestCase, WithdrawalFixtures):
    def setUp(self):
        self.user = make_user()
        self.admin = make_admin()
        self.admin.is_staff = True
        self.admin.save()
        self.fund_wallet(self.user)

    def test_request_reserves_amount_at_request_time(self):
        before = wallet_balance(self.user)
        request = self.create_request(self.user, "20000.00")
        self.assertEqual(wallet_balance(self.user), before - Decimal("20000.00"))
        self.assertEqual(request.status, WithdrawalRequest.Status.PENDING)
        rows = LedgerTransaction.objects.filter(
            user=self.user,
            type=LedgerTransaction.Type.WITHDRAWAL,
            reference=f"withdrawal:{request.reference}",
        )
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().amount, Decimal("-20000.00"))
        self.assertEqual(rows.first().status, LedgerTransaction.Status.COMPLETED)

    def test_ledger_reference_ties_request_and_ledger(self):
        request = self.create_request(self.user)
        debit_row = LedgerTransaction.objects.get(reference=f"withdrawal:{request.reference}")
        self.assertEqual(request.reference[:3], "WD-")
        self.assertIn(f"withdrawal:{request.reference}", debit_row.reference)

    def test_below_minimum_raises_without_rows(self):
        ledger_before = LedgerTransaction.objects.count()
        with self.assertRaises(Exception) as ctx:
            self.create_request(self.user, "400.00")
        self.assertIn("minimum", str(ctx.exception).lower())
        self.assertEqual(LedgerTransaction.objects.count(), ledger_before)
        self.assertEqual(WithdrawalRequest.objects.count(), 0)

    def test_insufficient_balance_raises_without_orphan_request(self):
        self.create_request(self.user, "100000.00")  # drains the balance
        self.assertEqual(wallet_balance(self.user), Decimal("0.00"))
        before_ids = set(WithdrawalRequest.objects.values_list("id", flat=True))
        with self.assertRaises(InsufficientBalance):
            self.create_request(self.user, "5000.00")
        after_ids = set(WithdrawalRequest.objects.values_list("id", flat=True))
        self.assertEqual(before_ids, after_ids)

    def test_float_inputs_rejected(self):
        with self.assertRaises(Exception) as ctx:
            WithdrawalService.request_withdrawal(
                self.user,
                amount=20000.0,
                provider=WithdrawalRequest.Provider.MPESA,
                mobile_money_number="255712345678",
            )
        self.assertIn("float", str(ctx.exception).lower())

    def test_request_without_funds_raises_insufficient(self):
        fresh = make_user("nofunds")
        with self.assertRaises(InsufficientBalance):
            WithdrawalService.request_withdrawal(
                fresh,
                amount=Decimal("5000.00"),
                provider=WithdrawalRequest.Provider.MPESA,
                mobile_money_number="255712345678",
            )


class WithdrawalTransitionTests(APITestCase, WithdrawalFixtures):
    def setUp(self):
        self.user = make_user()
        self.admin = make_admin()
        self.admin.is_staff = True
        self.admin.save()
        self.fund_wallet(self.user)
        self.request = self.create_request(self.user)

    def test_prefix_transitions(self):
        # PENDING -> PROCESSING (no ledger change)
        original = wallet_balance(self.user)
        self.request = WithdrawalService.process(self.request, actor=self.admin)
        self.assertEqual(self.request.status, WithdrawalRequest.Status.PROCESSING)
        self.assertEqual(wallet_balance(self.user), original)

        # PROCESSING -> COMPLETED (no ledger change; money already out)
        self.request = WithdrawalService.complete(self.request, actor=self.admin)
        self.assertEqual(self.request.status, WithdrawalRequest.Status.COMPLETED)
        self.assertEqual(wallet_balance(self.user), original)
        self.assertIsNotNone(self.request.processed_at)
        # Total withdrawn reflects the confirmed payout.
        summary = WalletService.balance_summary(self.user)
        self.assertEqual(summary["total_withdrawn"], Decimal("20000.00"))

    def test_fail_reverses_with_refund_in_same_transaction(self):
        # Balance was reduced to 80000 by the request; a FAIL refund must
        # restore the full 100000 the user was funded.
        self.request = WithdrawalService.process(self.request, actor=self.admin)
        self.request = WithdrawalService.fail(self.request, actor=self.admin)
        self.assertEqual(self.request.status, WithdrawalRequest.Status.FAILED)
        # The withdrawal debit (20000) is exactly offset by a REFUND (20000).
        self.assertEqual(wallet_balance(self.user), Decimal("100000.00"))
        refund = LedgerTransaction.objects.get(
            user=self.user,
            type=LedgerTransaction.Type.REFUND,
            reference=f"withdrawal:{self.request.reference}",
        )
        self.assertEqual(refund.amount, Decimal("20000.00"))
        self.assertEqual(refund.status, LedgerTransaction.Status.COMPLETED)

    def test_reject_from_pending_reverses(self):
        self.request = WithdrawalService.reject(self.request, actor=self.admin)
        self.assertEqual(self.request.status, WithdrawalRequest.Status.REJECTED)
        # Rejecting a PENDING request returns the funds to the full 100000.
        self.assertEqual(wallet_balance(self.user), Decimal("100000.00"))
        self.assertTrue(
            LedgerTransaction.objects.filter(
                user=self.user,
                type=LedgerTransaction.Type.REFUND,
                amount=Decimal("20000.00"),
            ).exists()
        )

    def test_terminal_request_cannot_be_reprocessed(self):
        self.request = WithdrawalService.process(self.request, actor=self.admin)
        self.request = WithdrawalService.complete(self.request, actor=self.admin)
        with self.assertRaises(Exception):
            WithdrawalService.fail(self.request, actor=self.admin)
        with self.assertRaises(Exception):
            WithdrawalService.complete(self.request, actor=self.admin)
        # Still exactly one refund net effect (zero for a completed payout).
        self.assertEqual(
            LedgerTransaction.objects.filter(
                user=self.user, type=LedgerTransaction.Type.REFUND
            ).count(),
            0,
        )

    def test_illegal_direct_complete_denied(self):
        # Cannot jump PENDING -> COMPLETED.
        with self.assertRaises(Exception) as ctx:
            WithdrawalService.complete(self.request, actor=self.admin)
        self.assertIn("cannot move", str(ctx.exception).lower())

    def test_non_staff_cannot_transition(self):
        with self.assertRaises(Exception) as ctx:
            WithdrawalService.process(self.request, actor=self.user)
        self.assertEqual(ctx.exception.code, "permission_denied")

    def test_double_fail_is_idempotent_reversal(self):
        WithdrawalService.process(self.request, actor=self.admin)
        WithdrawalService.fail(self.request, actor=self.admin)
        original = wallet_balance(self.user)
        with self.assertRaises(Exception):
            WithdrawalService.fail(self.request, actor=self.admin)
        self.assertEqual(wallet_balance(self.user), original)  # not refunded twice


class WithdrawalConcurrencyTests(TransactionTestCase, WithdrawalFixtures):
    def setUp(self):
        self.user = make_user()
        self.admin = make_admin()
        self.admin.is_staff = True
        self.admin.save()
        self.fund_wallet(self.user)
        self.request = self.create_request(self.user)
        WithdrawalService.process(self.request, actor=self.admin)

    def test_concurrent_complete_and_fail_act_exactly_once(self):
        barrier = threading.Barrier(2)
        errors: list[Exception] = []

        def worker(kind: str):
            close_old_connections()
            try:
                barrier.wait()
                if kind == "complete":
                    WithdrawalService.complete(self.request, actor=self.admin)
                else:
                    WithdrawalService.fail(self.request, actor=self.admin)
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [
            threading.Thread(target=worker, args=("complete",)),
            threading.Thread(target=worker, args=("fail",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        # Exactly one transition wins; the other raises (an allowed outcome).
        self.request.refresh_from_db()
        self.assertIn(
            self.request.status,
            [
                WithdrawalRequest.Status.COMPLETED,
                WithdrawalRequest.Status.FAILED,
            ],
        )
        # If it failed, exactly one refund exists. If completed, none.
        refund_count = LedgerTransaction.objects.filter(
            user=self.user, type=LedgerTransaction.Type.REFUND
        ).count()
        expected = 1 if self.request.status == WithdrawalRequest.Status.FAILED else 0
        self.assertEqual(refund_count, expected)


class WithdrawalApiTests(APITestCase, WithdrawalFixtures):
    def setUp(self):
        self.user = make_user()
        self.admin = make_admin()
        self.admin.is_staff = True
        self.admin.save()
        self.fund_wallet(self.user)
        auth(self.client, self.user)

    def test_create_requires_auth(self):
        fresh_client = self.client_class()
        response = fresh_client.post(
            WITHDRAWALS_URL,
            {
                "amount": "20000.00",
                "provider": "mpesa",
                "mobile_money_number": "255712345678",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_reduces_balance_and_returns_request(self):
        response = self.client.post(
            WITHDRAWALS_URL,
            {
                "amount": "20000.00",
                "provider": "mpesa",
                "mobile_money_number": "255712345678",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["amount"], "20000.00")
        self.assertEqual(data["provider"], "mpesa")
        self.assertEqual(wallet_balance(self.user), Decimal("80000.00"))

    def test_create_rejects_below_minimum(self):
        response = self.client.post(
            WITHDRAWALS_URL,
            {
                "amount": "400.00",
                "provider": "mpesa",
                "mobile_money_number": "255712345678",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_rejects_bad_number(self):
        response = self.client.post(
            WITHDRAWALS_URL,
            {
                "amount": "20000.00",
                "provider": "mpesa",
                "mobile_money_number": "123",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_returns_own_requests_only(self):
        self.create_request(self.user, "15000.00")
        other = make_user()
        self.fund_wallet(other)
        self.create_request(other, "15000.00")
        response = self.client.get(WITHDRAWALS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data["results"]}
        self.assertNotEqual(ids, set())
        # The other user's request is not visible.
        self.assertEqual(len(ids), 1)

    def test_admin_pending_requires_staff(self):
        response = self.client.get(f"{WITHDRAWALS_URL}admin/pending/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_pending_lists_queue(self):
        self.create_request(self.user, "20000.00")
        admin_client = self.client_class()
        auth(admin_client, self.admin)
        response = admin_client.get(f"{WITHDRAWALS_URL}admin/pending/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        statuses = {item["status"] for item in response.data["results"]}
        self.assertEqual(statuses, {"pending"})

    def test_admin_actions_require_staff_and_wire_transitions(self):
        request = self.create_request(self.user, "20000.00")
        # Non-staff gets 403.
        response = self.client.post(f"{WITHDRAWALS_URL}{request.id}/fail/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        admin_client = self.client_class()
        auth(admin_client, self.admin)

        process = admin_client.post(f"{WITHDRAWALS_URL}{request.id}/process/")
        self.assertEqual(process.status_code, status.HTTP_200_OK)
        request.refresh_from_db()
        self.assertEqual(request.status, "processing")

        fail = admin_client.post(
            f"{WITHDRAWALS_URL}{request.id}/fail/", {"admin_notes": "RTP error"}, format="json"
        )
        self.assertEqual(fail.status_code, status.HTTP_200_OK)
        request.refresh_from_db()
        self.assertEqual(request.status, "failed")
        self.assertEqual(request.admin_notes, "RTP error")
        self.assertEqual(wallet_balance(self.user), Decimal("100000.00"))

    def test_admin_reprocess_returns_400(self):
        request = self.create_request(self.user, "20000.00")
        admin_client = self.client_class()
        auth(admin_client, self.admin)
        admin_client.post(f"{WITHDRAWALS_URL}{request.id}/process/")
        admin_client.post(f"{WITHDRAWALS_URL}{request.id}/complete/")
        response = admin_client.post(f"{WITHDRAWALS_URL}{request.id}/complete/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PayoutIntegrationTests(APITestCase, WithdrawalFixtures):
    """ClickPesa auto-payout on withdrawal completion (Prompt 12 auto-payout)."""

    def setUp(self):
        self.user = make_user()
        self.admin = make_admin()
        self.fund_wallet(self.user)

    def test_phone_normalization(self):
        from withdrawals.payout import normalize_phone_number

        self.assertEqual(normalize_phone_number("0712345678"), "255712345678")
        self.assertEqual(normalize_phone_number("255712345678"), "255712345678")
        self.assertEqual(normalize_phone_number("+255 712 345 678"), "255712345678")

    def test_complete_with_payout_disabled_records_unavailable(self):
        from django.test import override_settings

        request = self.create_request(self.user, "20000.00")
        WithdrawalService.process(request, actor=self.admin)
        # Payouts disabled (default) -> graceful UNAVAILABLE, no network call.
        with override_settings(CLICKPESA_PAYOUTS_ENABLED=False):
            updated = WithdrawalService.complete(request, actor=self.admin)
        self.assertEqual(updated.status, "completed")
        self.assertEqual(updated.payout_status, "UNAVAILABLE")
        self.assertIn("disabled", updated.payout_message)
        # Money settled: funds stay out (no refund for a completed payout).
        self.assertEqual(wallet_balance(self.user), Decimal("80000.00"))

    def test_complete_records_gateway_success(self):
        from unittest import mock

        from django.test import override_settings

        request = self.create_request(self.user, "20000.00")
        WithdrawalService.process(request, actor=self.admin)
        fake_response = {
            "id": "PAY-123",
            "status": "SUCCESS",
            "amount": "20000.00",
            "currency": "TZS",
            "fee": "500.00",
        }
        with mock.patch(
            "payments.services.clickpesa_service.ClickPesaService.disburse",
            return_value=fake_response,
        ), override_settings(CLICKPESA_PAYOUTS_ENABLED=True):
            updated = WithdrawalService.complete(request, actor=self.admin)
        self.assertEqual(updated.status, "completed")
        self.assertEqual(updated.payout_status, "SUCCESS")
        self.assertEqual(updated.payout_reference, "PAY-123")

    def test_complete_graceful_fallback_on_gateway_error(self):
        from unittest import mock

        from django.test import override_settings

        from payments.services.clickpesa_service import ClickPesaError

        request = self.create_request(self.user, "20000.00")
        WithdrawalService.process(request, actor=self.admin)

        def _fail(*args, **kwargs):
            raise ClickPesaError(
                "Application has no access to PAYOUT API feature",
                status_code=400,
                response={"message": "Application has no access to PAYOUT API feature"},
            )

        with mock.patch(
            "payments.services.clickpesa_service.ClickPesaService.disburse",
            side_effect=_fail,
        ), override_settings(CLICKPESA_PAYOUTS_ENABLED=True):
            updated = WithdrawalService.complete(request, actor=self.admin)
        self.assertEqual(updated.status, "completed")  # never blocks completion
        self.assertEqual(updated.payout_status, "UNAVAILABLE")
        self.assertIn("PAYOUT API", updated.payout_message)
        # Completing did not reverse the reserved funds.
        self.assertEqual(wallet_balance(self.user), Decimal("80000.00"))
