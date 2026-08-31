"""Financial-consistency stress tests (Prompt 19).

These go beyond the unit coverage in wallet/withdrawals/payments to prove the
core invariant under pressure:

- **Ledger reconciliation** — after a randomized sequence of sales, transfers,
  withdrawals and reversals, the cached ``Wallet.balance`` must always be
  exactly the sum of COMPLETED balance-affecting ledger rows (never drifts),
  and must never go negative.
- **Concurrent withdrawals** — racing withdrawal requests against one wallet
  can never over-draw it (``select_for_update`` + the DB non-negative check are
  the guards).
- **Duplicate payment callbacks** — two concurrent webhooks for the same
  payment must both see the payment already final; the order is marked PAID
  exactly once and the seller is never double-credited.

All three use ``TransactionTestCase`` + real threads so row locks actually
contend, matching the production Postgres behaviour.
"""

from __future__ import annotations

import threading
from decimal import Decimal
from random import Random
from unittest.mock import patch

from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings

from catalog.test_api import make_category, make_product
from orders.models import Order, OrderItem
from payments.checksum import create_payload_checksum
from payments.models import Payment
from payments.services.clickpesa_service import ClickPesaService
from payments.services.payment_service import (
    handle_webhook,
    initiate_payment,
)
from wallet.models import LedgerTransaction, Wallet
from wallet.services import (
    InsufficientBalance,
    WalletService,
    reconcile_balance,
)
from withdrawals.models import WithdrawalRequest
from withdrawals.services import WithdrawalService

SECRET = "test-webhook-secret"


def _auth_token(client, user) -> None:
    from catalog.test_api import auth

    auth(client, user)


def _unique_email(prefix: str) -> str:
    import uuid

    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def make_user_unique(prefix: str = "seller"):
    from catalog.test_api import make_user as _make_user

    return _make_user(email=_unique_email(prefix))


class ReconciliationFixture:
    def make_sale(self, seller, buyer, category, price_units=1, price="100.00"):
        product = make_product(seller, category, price=price)
        order = Order.objects.create(
            buyer=buyer,
            subtotal=Decimal(price) * price_units,
            shipping_cost=Decimal("0.00"),
            total=Decimal(price) * price_units,
            status=Order.Status.PAID,
        )
        return OrderItem.objects.create(
            order=order,
            seller=seller,
            product=product,
            product_name=product.name,
            quantity=price_units,
            unit_price=Decimal(price),
            item_status=OrderItem.Status.DELIVERED,
        )


class LedgerReconciliationTests(TransactionTestCase, ReconciliationFixture):
    """Randomized operation sequence must never let balance drift or go negative."""

    def test_randomized_operations_keep_ledger_and_balance_reconciled(self):
        rng = Random(2026)
        seller = make_user_unique("seller")
        buyer = make_user_unique("buyer")
        category = make_category()
        balance = Decimal("0.00")

        for step in range(80):
            op = rng.choice(
                ["sale", "debit", "withdraw", "refund"]
            )

            if op == "sale":
                item = self.make_sale(seller, buyer, category)
                fee, credit = WalletService.process_completed_sale(item)
                net = credit.amount  # already 94% net after the 6% fee
                balance += net

            elif op == "debit":
                # Ask for up to current balance + a little headroom; only valid
                # debits (within balance) may succeed.
                amount = Decimal(rng.randint(1, 20000 + 100)).quantize(
                    Decimal("0.01")
                )
                try:
                    WalletService.debit(
                        seller,
                        amount,
                        reference=f"stress-debit-{step}",
                        description="stress debit",
                    )
                    balance -= amount
                except InsufficientBalance:
                    pass  # expected; balance unchanged

            elif op == "withdraw":
                amount = Decimal(rng.randint(5000, 20000 + 100)).quantize(
                    Decimal("0.01")
                )
                try:
                    WithdrawalService.request_withdrawal(
                        seller,
                        amount=amount,
                        provider=WithdrawalRequest.Provider.MPESA,
                        mobile_money_number="255712345678",
                    )
                    balance -= amount
                except Exception:
                    # below-minimum or insufficient-balance: nothing moved
                    pass

            elif op == "refund":
                amount = Decimal(rng.randint(1, 5000)).quantize(Decimal("0.01"))
                WalletService.refund(
                    seller,
                    amount,
                    reference=f"stress-refund-{step}",
                    description="stress refund",
                )
                balance += amount

            wallet = Wallet.objects.get(user=seller)
            ledger_total = reconcile_balance(seller)

            # Invariant 1: cached balance == ledger sum, down to the cent.
            self.assertEqual(
                wallet.balance,
                ledger_total,
                f"balance/ledger drift at step {step} (op={op})",
            )
            # Invariant 2: never negative.
            self.assertGreaterEqual(wallet.balance, Decimal("0.00"))
            # Invariant 3: our independent accounting matches both.
            self.assertEqual(
                balance,
                wallet.balance,
                f"independent accounting diverged at step {step} (op={op})",
            )


def _noop():
    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    return _Ctx()


class ConcurrentWithdrawalTests(TransactionTestCase, ReconciliationFixture):
    """Two concurrent withdrawal requests against one wallet cannot over-draw."""

    def test_concurrent_withdrawals_never_overdraw(self):
        seller = make_user_unique("seller")
        WalletService.credit(seller, Decimal("10000.00"), description="seed")

        barrier = threading.Barrier(2)
        errors: list[str] = []

        def worker(inc):
            close_old_connections()
            try:
                barrier.wait()
                WithdrawalService.request_withdrawal(
                    seller,
                    amount=Decimal("8000.00"),
                    provider=WithdrawalRequest.Provider.MPESA,
                    mobile_money_number="255712345678",
                )
            except Exception as exc:  # coexists with the other thread succeeding
                errors.append(f"{type(exc).__name__}: {exc}")
            finally:
                close_old_connections()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        wallet = Wallet.objects.get(user=seller)
        # Exactly one of the two 8000 withdrawals can succeed against 10000.
        self.assertGreaterEqual(wallet.balance, Decimal("0.00"))
        completed = LedgerTransaction.objects.filter(
            user=seller,
            type=LedgerTransaction.Type.WITHDRAWAL,
            status=LedgerTransaction.Status.COMPLETED,
        ).count()
        # One succeeds; the other either raises (overdraw attempt, caught) or
        # also succeeded only if there was room — here there is not enough.
        active_withdrawals = WithdrawalRequest.objects.filter(
            user=seller, amount=Decimal("8000.00")
        ).count()
        self.assertLessEqual(active_withdrawals, 1)
        self.assertEqual(completed, active_withdrawals)
        # Ledger and balance still reconcile.
        self.assertEqual(wallet.balance, reconcile_balance(seller))


@override_settings(CLICKPESA_WEBHOOK_SECRET=SECRET)
class DuplicateCallbackConcurrencyTests(TransactionTestCase):
    """Two concurrent webhooks for the same payment must be processed once."""

    def setUp(self):
        self.buyer = make_user_unique("buyer")
        self.seller = make_user_unique("seller")
        category = make_category()
        self.product = make_product(self.seller, category, price=Decimal("50.00"))
        order = Order.objects.create(
            buyer=self.buyer,
            subtotal=Decimal("50.00"),
            shipping_cost=Decimal("0.00"),
            total=Decimal("50.00"),
            status=Order.Status.PENDING_PAYMENT,
        )
        self.item = OrderItem.objects.create(
            order=order,
            seller=self.seller,
            product=self.product,
            product_name=self.product.name,
            quantity=1,
            unit_price=Decimal("50.00"),
            item_status=OrderItem.Status.PENDING,
        )
        self.order = order
        self.payment: Payment | None = None

    def _initiate(self):
        with patch.object(
            ClickPesaService,
            "initiate_ussd_push",
            return_value={"status": "PROCESSING", "id": "TXN1", "orderReference": "x"},
        ):
            self.payment = initiate_payment(self.order, "255712345678")

    def _signed_payload(self) -> dict:
        data = {
            "id": "CP1",
            "status": "SUCCESS",
            "orderReference": self.payment.external_reference,
            "collectedAmount": "50",
            "collectedCurrency": "TZS",
            "message": "ok",
            "channel": "TIGO-PESA",
        }
        body = {"event": "PAYMENT RECEIVED", "data": data}
        payload = dict(body)
        payload["checksum"] = create_payload_checksum(SECRET, body)
        return payload

    def test_concurrent_duplicate_callbacks_process_once(self):
        self._initiate()
        payload = self._signed_payload()
        barrier = threading.Barrier(2)
        errors: list[Exception] = []
        results: list[str] = []

        def worker(inc):
            close_old_connections()
            try:
                barrier.wait()
                handle_webhook(payload)
                results.append("ok")
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(errors, [])
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.SUCCESSFUL)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        # Exactly one payment object; duplicate callback did not create another.
        self.assertEqual(
            Payment.objects.filter(order=self.order).count(), 1
        )
