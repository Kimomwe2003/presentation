"""Wallet + ledger tests (Prompt 10).

Covers the acceptance criteria:
- exact 6% fee math with Decimal (100,000 TZS sale -> 6,000 fee + 94,000 net)
- ledger is the source of truth; the cached balance reconciles to it
- idempotency: double invocation produces one fee/credit pair
- concurrency: racing invocations (two threads) do not double-credit
- negative-balance guard rejects an over-debit, at service and DB level
- code-review rule: no float is used for money in wallet/orders/payments
- API: balance summary, paginated + filterable transactions, auth, and the
  full order-completion flow credits the seller exactly once
"""

import ast
import threading
from decimal import Decimal
from pathlib import Path

from django.db import IntegrityError, close_old_connections, transaction
from django.test import TransactionTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.test_api import auth, make_category, make_product, make_user
from orders.models import Order, OrderItem
from wallet.models import LedgerTransaction
from wallet.services import InsufficientBalance, WalletError, WalletService

BALANCE_URL = "/api/wallet/balance/"
PENDING_EARNINGS_URL = "/api/wallet/pending-earnings/"
TRANSACTIONS_URL = "/api/wallet/transactions/"
ORDERS_URL = "/api/orders/"


class SaleFixtures:
    """Create a PAID order with one DELIVERED item for a given unit price."""

    def create_sale(self, price="100000.00"):
        self.buyer = make_user("buyer@example.com")
        self.seller = make_user("seller@example.com")
        self.category = make_category()
        self.product = make_product(self.seller, self.category, price=price)
        self.order = Order.objects.create(
            buyer=self.buyer,
            subtotal=Decimal(price),
            shipping_cost=Decimal("0.00"),
            total=Decimal(price),
            status=Order.Status.PAID,
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            seller=self.seller,
            product=self.product,
            product_name=self.product.name,
            quantity=1,
            unit_price=Decimal(price),
            item_status=OrderItem.Status.DELIVERED,
        )
        return self.item


# ---------------------------------------------------------------------------
# Service: fee math, balance, idempotency, guards
# ---------------------------------------------------------------------------


class WalletServiceTests(APITestCase, SaleFixtures):
    def setUp(self):
        self.create_sale()

    def test_100k_sale_fee_and_net_exact(self):
        fee_row, credit_row = WalletService.process_completed_sale(self.item)

        self.assertEqual(fee_row.type, LedgerTransaction.Type.PLATFORM_FEE)
        self.assertEqual(fee_row.amount, Decimal("-6000.00"))
        self.assertEqual(credit_row.type, LedgerTransaction.Type.CREDIT)
        self.assertEqual(credit_row.amount, Decimal("94000.00"))
        self.assertEqual(fee_row.order_item_id, self.item.pk)
        self.assertEqual(credit_row.order_item_id, self.item.pk)

        self.seller.wallet.refresh_from_db()
        self.assertEqual(self.seller.wallet.balance, Decimal("94000.00"))

    def test_fee_precision_with_cents(self):
        self.item.unit_price = Decimal("1234.56")
        self.item.save(update_fields=["unit_price"])

        fee_row, credit_row = WalletService.process_completed_sale(self.item)

        # 1234.56 * 0.06 = 74.0736 -> fee 74.07 (rounded half-up), net 1160.49.
        self.assertEqual(fee_row.amount, Decimal("-74.07"))
        self.assertEqual(credit_row.amount, Decimal("1160.49"))
        self.assertEqual(-fee_row.amount + credit_row.amount, Decimal("1234.56"))

    def test_balance_equals_ledger_sum(self):
        WalletService.process_completed_sale(self.item)
        # A second completed sale for the same seller.
        item2 = OrderItem.objects.create(
            order=self.order,
            seller=self.seller,
            product=self.product,
            product_name="Second item",
            quantity=2,
            unit_price=Decimal("50.00"),
            item_status=OrderItem.Status.DELIVERED,
        )
        WalletService.process_completed_sale(item2)

        self.seller.wallet.refresh_from_db()
        expected = sum(
            LedgerTransaction.objects.filter(
                user=self.seller,
                status=LedgerTransaction.Status.COMPLETED,
                type=LedgerTransaction.Type.CREDIT,
            ).values_list("amount", flat=True),
            Decimal("0.00"),
        )
        self.assertEqual(self.seller.wallet.balance, expected)
        self.assertEqual(self.seller.wallet.balance, Decimal("94000.00") + Decimal("94.00"))

    def test_double_invocation_is_idempotent(self):
        first = WalletService.process_completed_sale(self.item)
        second = WalletService.process_completed_sale(self.item)

        self.assertEqual(second[0].pk, first[0].pk)
        self.assertEqual(second[1].pk, first[1].pk)
        self.assertEqual(
            LedgerTransaction.objects.filter(
                order_item=self.item, type=LedgerTransaction.Type.CREDIT
            ).count(),
            1,
        )
        self.assertEqual(
            LedgerTransaction.objects.filter(
                order_item=self.item, type=LedgerTransaction.Type.PLATFORM_FEE
            ).count(),
            1,
        )
        self.seller.wallet.refresh_from_db()
        self.assertEqual(self.seller.wallet.balance, Decimal("94000.00"))

    def test_sale_without_seller_is_noop(self):
        self.item.seller = None
        self.item.save(update_fields=["seller"])
        self.assertIsNone(WalletService.process_completed_sale(self.item))
        self.assertEqual(LedgerTransaction.objects.count(), 0)

    def test_debit_guard_rejects_over_debit(self):
        WalletService.process_completed_sale(self.item)

        with self.assertRaises(InsufficientBalance):
            WalletService.debit(self.seller, Decimal("94000.01"))

        self.seller.wallet.refresh_from_db()
        self.assertEqual(self.seller.wallet.balance, Decimal("94000.00"))
        self.assertEqual(
            LedgerTransaction.objects.filter(
                user=self.seller, type=LedgerTransaction.Type.DEBIT
            ).count(),
            0,
        )

    def test_debit_within_balance_applies(self):
        WalletService.process_completed_sale(self.item)
        row = WalletService.debit(self.seller, Decimal("9000.00"), description="test debit")

        self.assertEqual(row.amount, Decimal("-9000.00"))
        self.seller.wallet.refresh_from_db()
        self.assertEqual(self.seller.wallet.balance, Decimal("85000.00"))

    def test_float_inputs_rejected(self):
        with self.assertRaises(WalletError):
            WalletService.credit(self.seller, 10.0)
        with self.assertRaises(WalletError):
            WalletService.debit(self.seller, 5.0)

    def test_db_constraint_blocks_negative_balance(self):
        wallet = self.seller.wallet
        wallet.balance = Decimal("-1.00")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                wallet.save(update_fields=["balance"])

    def test_credit_increases_balance(self):
        WalletService.credit(self.seller, Decimal("100.00"), description="manual credit")
        self.seller.wallet.refresh_from_db()
        self.assertEqual(self.seller.wallet.balance, Decimal("100.00"))

    def test_balance_summary_totals(self):
        WalletService.process_completed_sale(self.item)
        summary = WalletService.balance_summary(self.seller)

        self.assertEqual(summary["balance"], Decimal("94000.00"))
        self.assertEqual(summary["total_earnings"], Decimal("94000.00"))
        self.assertEqual(summary["total_withdrawn"], Decimal("0.00"))

    def test_pending_earnings_net_of_fee(self):
        # One DELIVERED item at 100,000, not yet completed -> projected 94,000.
        self.assertEqual(
            WalletService.pending_earnings(self.seller), Decimal("94000.00")
        )

    def test_pending_earnings_excludes_completed_cancelled_and_unpaid(self):
        # The DELIVERED sale item completes (as transition_item would do).
        self.item.item_status = OrderItem.Status.COMPLETED
        self.item.save(update_fields=["item_status"])
        WalletService.process_completed_sale(self.item)
        # In-transit item: 2 x 10.00 -> 20.00 -> 18.80 (94%).
        OrderItem.objects.create(
            order=self.order,
            seller=self.seller,
            product=self.product,
            product_name="In transit",
            quantity=2,
            unit_price=Decimal("10.00"),
            item_status=OrderItem.Status.SHIPPED,
        )
        # Cancelled items never count as pending.
        OrderItem.objects.create(
            order=self.order,
            seller=self.seller,
            product=self.product,
            product_name="Cancelled line",
            quantity=1,
            unit_price=Decimal("100.00"),
            item_status=OrderItem.Status.CANCELLED,
        )
        # Items on an unpaid order are not sold yet.
        unpaid = Order.objects.create(
            buyer=self.buyer,
            subtotal=Decimal("5.00"),
            total=Decimal("5.00"),
            status=Order.Status.PENDING_PAYMENT,
        )
        OrderItem.objects.create(
            order=unpaid,
            seller=self.seller,
            product=self.product,
            product_name="Not paid",
            quantity=1,
            unit_price=Decimal("5.00"),
            item_status=OrderItem.Status.PENDING,
        )

        self.assertEqual(
            WalletService.pending_earnings(self.seller), Decimal("18.80")
        )


# ---------------------------------------------------------------------------
# Concurrency: racing completions must not double-credit (select_for_update)
# ---------------------------------------------------------------------------


class ConcurrentCompletionTests(TransactionTestCase, SaleFixtures):
    def setUp(self):
        self.create_sale()

    def test_concurrent_completion_credits_exactly_once(self):
        barrier = threading.Barrier(2)
        errors: list[Exception] = []

        def worker():
            close_old_connections()
            try:
                barrier.wait()
                WalletService.process_completed_sale(self.item)
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(errors, [])
        self.assertEqual(
            LedgerTransaction.objects.filter(
                order_item=self.item, type=LedgerTransaction.Type.CREDIT
            ).count(),
            1,
        )
        self.assertEqual(
            LedgerTransaction.objects.filter(
                order_item=self.item, type=LedgerTransaction.Type.PLATFORM_FEE
            ).count(),
            1,
        )
        self.seller.wallet.refresh_from_db()
        self.assertEqual(self.seller.wallet.balance, Decimal("94000.00"))


# ---------------------------------------------------------------------------
# Code review: money is Decimal everywhere, never float
# ---------------------------------------------------------------------------

MONEY_MODULES = [
    "wallet/models.py",
    "wallet/services.py",
    "wallet/serializers.py",
    "wallet/views.py",
    "orders/models.py",
    "orders/services.py",
    "orders/serializers.py",
    "orders/state_machine.py",
    "payments/models.py",
    "payments/serializers.py",
    "payments/checksum.py",
    "payments/services/payment_service.py",
    "withdrawals/models.py",
    "withdrawals/services.py",
    "withdrawals/serializers.py",
]


def test_no_float_used_for_money():
    """Code-review rule: financial code uses Decimal, never float.

    Note: payments/services/clickpesa_service.py is intentionally excluded —
    its only float use is ``time.monotonic()`` timestamps, not money.
    """
    backend = Path(__file__).resolve().parent.parent
    for relative in MONEY_MODULES:
        tree = ast.parse((backend / relative).read_text(encoding="utf-8"))
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                offenders.append(f"line {node.lineno}: float literal {node.value!r}")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "float"
            ):
                offenders.append(f"line {node.lineno}: float() call")
        assert not offenders, f"{relative} uses float for money: {offenders}"


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


class WalletApiTests(APITestCase, SaleFixtures):
    def setUp(self):
        self.create_sale()
        auth(self.client, self.seller)

    def test_balance_requires_auth(self):
        self.client.credentials()
        response = self.client.get(BALANCE_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_balance_summary_endpoint(self):
        WalletService.process_completed_sale(self.item)
        response = self.client.get(BALANCE_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["balance"], "94000.00")
        self.assertEqual(response.data["total_earnings"], "94000.00")
        self.assertEqual(response.data["total_withdrawn"], "0.00")

    def test_balance_is_zero_before_any_sale(self):
        response = self.client.get(BALANCE_URL)
        self.assertEqual(response.data["balance"], "0.00")
        self.assertEqual(response.data["total_earnings"], "0.00")

    def test_transactions_list_is_paginated_and_own_only(self):
        WalletService.process_completed_sale(self.item)
        other = make_user("other@example.com")
        WalletService.credit(other, Decimal("10.00"), description="someone else's money")

        response = self.client.get(TRANSACTIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)  # fee + credit for the seller
        rows = response.data["results"]
        self.assertEqual({r["type"] for r in rows}, {"platform_fee", "credit"})
        # Newest first.
        self.assertEqual(rows[0]["type"], "credit")

    def test_transactions_filter_by_type(self):
        WalletService.process_completed_sale(self.item)
        response = self.client.get(TRANSACTIONS_URL, {"type": "platform_fee"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["type"], "platform_fee")
        self.assertEqual(response.data["results"][0]["amount"], "-6000.00")
        self.assertEqual(response.data["results"][0]["order_item_id"], self.item.pk)

    def test_transactions_filter_by_date_range(self):
        WalletService.process_completed_sale(self.item)
        # Backdate a second sale's rows to yesterday.
        item2 = OrderItem.objects.create(
            order=self.order,
            seller=self.seller,
            product=self.product,
            product_name="Old item",
            quantity=1,
            unit_price=Decimal("10.00"),
            item_status=OrderItem.Status.DELIVERED,
        )
        WalletService.process_completed_sale(item2)
        LedgerTransaction.objects.filter(order_item=item2).update(
            created_at="2020-01-01T00:00:00Z"
        )

        response = self.client.get(
            TRANSACTIONS_URL, {"from": "2019-12-31", "to": "2020-01-02"}
        )
        self.assertEqual(response.data["count"], 2)
        self.assertEqual({r["order_item_id"] for r in response.data["results"]}, {item2.pk})

    def test_transactions_reject_invalid_date(self):
        response = self.client.get(TRANSACTIONS_URL, {"from": "not-a-date"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_type_filter_is_empty(self):
        response = self.client.get(TRANSACTIONS_URL, {"type": "bogus"})
        self.assertEqual(response.data["count"], 0)

    def test_pending_earnings_requires_auth(self):
        self.client.credentials()
        response = self.client.get(PENDING_EARNINGS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pending_earnings_endpoint(self):
        # DELIVERED, not completed -> 94% of 100,000 projected.
        response = self.client.get(PENDING_EARNINGS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pending_earnings"], "94000.00")

    def test_pending_earnings_is_per_user(self):
        other = make_user("other@example.com")
        auth(self.client, other)
        response = self.client.get(PENDING_EARNINGS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pending_earnings"], "0.00")

    def test_pending_earnings_zero_after_completion(self):
        self.item.item_status = OrderItem.Status.COMPLETED
        self.item.save(update_fields=["item_status"])
        WalletService.process_completed_sale(self.item)
        response = self.client.get(PENDING_EARNINGS_URL)
        self.assertEqual(response.data["pending_earnings"], "0.00")

    def test_completed_sale_flow_credits_seller(self):
        """The full order lifecycle (pay -> complete) credits the seller via the hook."""
        auth(self.client, self.buyer)
        order = self.order
        order.status = Order.Status.PENDING_PAYMENT
        order.save(update_fields=["status"])
        item = order.items.first()
        item.item_status = OrderItem.Status.PENDING
        item.save(update_fields=["item_status"])

        def act(user, path):
            auth(self.client, user)
            return self.client.post(path, {}, format="json")

        # Admin marks paid (Prompt 09 normally moves PAID on a webhook).
        from orders.services import mark_order_paid

        mark_order_paid(order, actor="payment")
        self.assertEqual(act(self.seller, f"{ORDERS_URL}items/{item.pk}/confirm/").status_code, 200)
        self.assertEqual(act(self.seller, f"{ORDERS_URL}items/{item.pk}/ship/").status_code, 200)
        self.assertEqual(act(self.seller, f"{ORDERS_URL}items/{item.pk}/deliver/").status_code, 200)
        self.assertEqual(act(self.buyer, f"{ORDERS_URL}items/{item.pk}/complete/").status_code, 200)

        item.refresh_from_db()
        self.assertEqual(item.item_status, OrderItem.Status.COMPLETED)
        auth(self.client, self.seller)
        response = self.client.get(BALANCE_URL)
        self.assertEqual(response.data["balance"], "94000.00")
        self.assertEqual(
            LedgerTransaction.objects.filter(order_item=item).count(), 2
        )
