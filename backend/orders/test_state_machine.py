"""State-machine / lifecycle tests for order + item transitions (Prompt 08).

Covers every defined transition: allowed flows succeed, and disallowed flows
(wrong role, wrong current state, missing payment) are rejected with 400/403.
"""

from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from catalog.test_api import auth, make_category, make_product, make_user
from orders.models import Order, OrderItem

ORDERS_URL = "/api/orders/"


class LifecycleBase(APITestCase):
    def setUp(self):
        self.buyer = make_user("buyer@example.com")
        self.seller = make_user("seller@example.com")
        self.admin = make_user("admin@example.com")
        self.admin.is_staff = True
        self.admin.save()
        self.category = make_category()
        self.product = make_product(self.seller, self.category, price=Decimal("50.00"))
        auth(self.client, self.buyer)
        self.order = self._create_order()

    def _create_order(self):
        self.client.post(
            "/api/cart/items/",
            {"product_id": self.product.pk, "quantity": 1},
            format="json",
        )
        response = self.client.post(
            ORDERS_URL, {"payment_method": "card"}, format="json"
        )
        return Order.objects.get(pk=response.data["id"])

    def _mark_paid(self):
        auth(self.client, self.admin)
        response = self.client.post(
            f"{ORDERS_URL}{self.order.pk}/mark-paid/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        auth(self.client, self.buyer)
        return response

    def _item(self):
        return self.order.items.first()

    def _act(self, user, path):
        auth(self.client, user)
        return self.client.post(path, {}, format="json")


class OrderTransitionTests(LifecycleBase):
    # -- Order-level: cancel ------------------------------------------------

    def test_buyer_cancels_before_payment(self):
        response = self._act(self.buyer, f"{ORDERS_URL}{self.order.pk}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Order.Status.CANCELLED)

    def test_buyer_cannot_cancel_after_payment(self):
        self._mark_paid()
        response = self._act(self.buyer, f"{ORDERS_URL}{self.order.pk}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_seller_cannot_cancel_buyers_order(self):
        # The seller is a party to the order (their item is in it) so they get
        # a clear 403 — but the state machine still rejects the wrong role.
        response = self._act(self.seller, f"{ORDERS_URL}{self.order.pk}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_stranger_cannot_cancel(self):
        stranger = make_user("stranger@example.com")
        response = self._act(stranger, f"{ORDERS_URL}{self.order.pk}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_cannot_cancel(self):
        self.client.credentials()
        response = self.client.post(
            f"{ORDERS_URL}{self.order.pk}/cancel/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # -- Order-level: mark paid --------------------------------------------

    def test_buyer_cannot_mark_paid(self):
        response = self._act(self.buyer, f"{ORDERS_URL}{self.order.pk}/mark-paid/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_seller_cannot_mark_paid(self):
        response = self._act(self.seller, f"{ORDERS_URL}{self.order.pk}/mark-paid/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_marks_paid(self):
        response = self._mark_paid()
        self.assertEqual(response.data["status"], Order.Status.PAID)

    def test_mark_paid_rejected_when_already_paid(self):
        self._mark_paid()
        response = self._act(self.admin, f"{ORDERS_URL}{self.order.pk}/mark-paid/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mark_paid_credits_seller_wallet_and_marks_product_sold(self):
        from catalog.models import Product
        from wallet.models import Wallet
        from wallet.services import PLATFORM_FEE_RATE

        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.ACTIVE)
        wallet, _ = Wallet.objects.get_or_create(user=self.seller)
        self.assertEqual(wallet.balance, Decimal("0.00"))

        self._mark_paid()

        # Seller's wallet is credited net of the 6% platform fee at sale time.
        wallet.refresh_from_db()
        expected = Decimal("50.00") * (Decimal("1") - PLATFORM_FEE_RATE)
        self.assertEqual(wallet.balance, expected.quantize(Decimal("0.01")))

        # The product is now SOLD — no longer for sale.
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.SOLD)

    def test_sold_product_hidden_from_admin_listing(self):
        auth(self.client, self.admin)
        response = self.client.get("/api/products/")
        self.assertTrue(any(p["id"] == self.product.pk for p in response.data["results"]))

        self._mark_paid()

        response = self.client.get("/api/products/")
        self.assertFalse(any(p["id"] == self.product.pk for p in response.data["results"]))

    # -- Order-level: admin refund ------------------------------------------

    def test_admin_can_refund_paid_order(self):
        self._mark_paid()
        response = self._act(self.admin, f"{ORDERS_URL}{self.order.pk}/refund/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Order.Status.REFUNDED)

    def test_buyer_cannot_refund(self):
        self._mark_paid()
        response = self._act(self.buyer, f"{ORDERS_URL}{self.order.pk}/refund/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_refund_before_paid(self):
        response = self._act(self.admin, f"{ORDERS_URL}{self.order.pk}/refund/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ItemTransitionTests(LifecycleBase):
    def setUp(self):
        super().setUp()
        self._mark_paid()
        self.item = self._item()

    def item_url(self, action):
        return f"{ORDERS_URL}items/{self.item.pk}/{action}/"

    # -- Confirm (seller) ---------------------------------------------------

    def test_seller_confirms_item(self):
        response = self._act(self.seller, self.item_url("confirm"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"][0]["item_status"], OrderItem.Status.CONFIRMED)

    def test_buyer_cannot_confirm_own_item(self):
        response = self._act(self.buyer, self.item_url("confirm"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_user_cannot_confirm(self):
        stranger = make_user("stranger@example.com")
        response = self._act(stranger, self.item_url("confirm"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # -- Ship (seller) ------------------------------------------------------

    def test_seller_ships_confirmed_item(self):
        self._act(self.seller, self.item_url("confirm"))
        response = self._act(self.seller, self.item_url("ship"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"][0]["item_status"], OrderItem.Status.SHIPPED)

    def test_buyer_cannot_ship(self):
        self._act(self.seller, self.item_url("confirm"))
        response = self._act(self.buyer, self.item_url("ship"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_ship_before_confirm(self):
        response = self._act(self.seller, self.item_url("ship"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # -- Deliver (seller) ---------------------------------------------------

    def test_seller_delivers_shipped_item(self):
        self._act(self.seller, self.item_url("confirm"))
        self._act(self.seller, self.item_url("ship"))
        response = self._act(self.seller, self.item_url("deliver"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"][0]["item_status"], OrderItem.Status.DELIVERED)

    def test_cannot_deliver_before_ship(self):
        response = self._act(self.seller, self.item_url("deliver"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # -- Complete (buyer confirms receipt) ----------------------------------

    def test_full_flow_to_completed(self):
        self._act(self.seller, self.item_url("confirm"))
        self._act(self.seller, self.item_url("ship"))
        self._act(self.seller, self.item_url("deliver"))
        response = self._act(self.buyer, self.item_url("complete"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"][0]["item_status"], OrderItem.Status.COMPLETED)
        # Envelope auto-completes when the only item completes.
        self.assertEqual(response.data["status"], Order.Status.COMPLETED)

    def test_seller_cannot_complete(self):
        self._act(self.seller, self.item_url("confirm"))
        self._act(self.seller, self.item_url("ship"))
        self._act(self.seller, self.item_url("deliver"))
        response = self._act(self.seller, self.item_url("complete"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_complete_before_delivered(self):
        response = self._act(self.buyer, self.item_url("complete"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PaymentPreconditionTests(LifecycleBase):
    """Fulfillment is gated on the order being paid (no payment yet -> blocked)."""

    def test_seller_cannot_confirm_unpaid_order(self):
        response = self._act(self.seller, f"{ORDERS_URL}items/{self._item().pk}/confirm/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_available_actions_only_after_payment(self):
        auth(self.client, self.seller)
        response = self.client.get(f"{ORDERS_URL}selling/{self.order.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Unpaid order -> seller has no item actions yet.
        self.assertEqual(response.data["items"][0]["available_actions"], [])

        self._mark_paid()
        auth(self.client, self.seller)
        response = self.client.get(f"{ORDERS_URL}selling/{self.order.pk}/")
        actions = response.data["items"][0]["available_actions"]
        self.assertIn("confirm", [a["action"] for a in actions])
