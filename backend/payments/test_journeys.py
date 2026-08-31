"""Automated end-to-end journey tests (Prompt 18).

These exercise both the full buyer and seller journeys through the real HTTP
API (ClickPesa mocked at the service boundary), proving each step works without
manual backend intervention. They double as the automated counterpart to the
manual E2E checklist in docs/ARCHITECTURE.md.
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Product
from catalog.test_api import auth, make_category, make_product, make_user
from orders.models import Order
from payments.models import Payment
from payments.services.clickpesa_service import ClickPesaService

from .test_payments import SECRET, WEBHOOK_URL, signed

INITIATE_URL = "/api/payments/initiate/"


@override_settings(CLICKPESA_WEBHOOK_SECRET=SECRET)
class BuyerJourneyTests(APITestCase):
    """register → browse → add to cart → checkout → pay → track → receive → review."""

    def setUp(self):
        self.seller = make_user("seller@example.com")
        self.category = make_category()
        self.product = make_product(self.seller, self.category, price=Decimal("50.00"))

    def test_full_buyer_journey(self):
        # 1. Register a new buyer.
        register = self.client.post(
            "/api/auth/register/",
            {
                "email": "buyer@example.com",
                "password": "Str0ng!Pass",
                "password_confirmation": "Str0ng!Pass",
                "full_name": "Brenda Buyer",
            },
            format="json",
        )
        self.assertEqual(register.status_code, status.HTTP_201_CREATED, register.data)
        buyer = get_user_model().objects.get(email="buyer@example.com")
        auth(self.client, buyer)

        # 2. Browse the marketplace (public feed lists the active product).
        feed = self.client.get("/api/products/")
        self.assertEqual(feed.status_code, status.HTTP_200_OK)
        self.assertEqual(feed.data["count"], 1)

        # 3. Add to cart.
        add = self.client.post(
            "/api/cart/items/",
            {"product_id": self.product.pk, "quantity": 1},
            format="json",
        )
        self.assertEqual(add.status_code, status.HTTP_201_CREATED)
        cart = self.client.get("/api/cart/")
        self.assertEqual(cart.data["item_count"], 1)

        # 4. Checkout (create order from the current cart).
        order_resp = self.client.post("/api/orders/", {"payment_method": "card"}, format="json")
        self.assertEqual(order_resp.status_code, status.HTTP_201_CREATED)
        order_id = order_resp.data["id"]
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.status, Order.Status.PENDING_PAYMENT)
        # The cart is drained by checkout.
        self.assertEqual(self.client.get("/api/cart/").data["item_count"], 0)

        # 5. Pay — initiate, then a successful ClickPesa webhook marks it paid.
        with patch.object(
            ClickPesaService,
            "initiate_ussd_push",
            return_value={"status": "PROCESSING", "id": "TXN1", "orderReference": "ref1"},
        ):
            initiate = self.client.post(
                INITIATE_URL,
                {"order_id": order_id, "phone_number": "255712345678"},
                format="json",
            )
            self.assertEqual(initiate.status_code, status.HTTP_201_CREATED)
        payment = Payment.objects.get(order=order)
        webhook = self.client.post(
            WEBHOOK_URL,
            signed(
                {
                    "event": "PAYMENT RECEIVED",
                    "data": {
                        "id": "CP1",
                        "status": "SUCCESS",
                        "orderReference": payment.external_reference,
                        "collectedAmount": "50",
                        "collectedCurrency": "TZS",
                        "message": "ok",
                        "channel": "TIGO-PESA",
                    },
                }
            ),
            format="json",
        )
        self.assertEqual(webhook.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

        # 6. Track order (buyer sees it in their list/detail).
        tracked = self.client.get(f"/api/orders/{order_id}/")
        self.assertEqual(tracked.status_code, status.HTTP_200_OK)
        self.assertEqual(tracked.data["status"], "paid")

        # 7. Seller fulfils (confirm → ship → deliver), then buyer receives (complete).
        item_id = order.items.get().pk
        for action in ("confirm", "ship", "deliver", "complete"):
            url = {
                "confirm": f"/api/orders/items/{item_id}/confirm/",
                "ship": f"/api/orders/items/{item_id}/ship/",
                "deliver": f"/api/orders/items/{item_id}/deliver/",
                "complete": f"/api/orders/items/{item_id}/complete/",
            }[action]
            actor = self.seller if action != "complete" else buyer
            auth(self.client, actor)
            resp = self.client.post(url)
            self.assertEqual(resp.status_code, status.HTTP_200_OK, f"{action}: {resp.data}")

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)
        # Delivery completion releases earnings to the seller's wallet.
        self.assertGreater(Decimal(self._seller_balance()), Decimal("0.00"))

        # 8. Buyer reviews the completed item.
        auth(self.client, buyer)
        review = self.client.post(
            "/api/reviews/",
            {"order_item_id": item_id, "rating": 5, "comment": "Great!"},
            format="json",
        )
        self.assertEqual(review.status_code, status.HTTP_201_CREATED, review.data)

    def _seller_balance(self):
        auth(self.client, self.seller)
        resp = self.client.get("/api/wallet/balance/")
        return resp.data["balance"]


@override_settings(CLICKPESA_WEBHOOK_SECRET=SECRET)
class SellerJourneyTests(APITestCase):
    """register (seller) → list → receive order → fulfil → get paid → see earnings → withdraw."""

    def test_full_seller_journey(self):
        # 1. Register the seller.
        self.client.post(
            "/api/auth/register/",
            {
                "email": "seller@example.com",
                "password": "Str0ng!Pass",
                "password_confirmation": "Str0ng!Pass",
                "full_name": "Sam Seller",
            },
            format="json",
        )
        seller = get_user_model().objects.get(email="seller@example.com")
        auth(self.client, seller)

        # 2. List a product (create → activate).
        created = self.client.post(
            "/api/products/",
            {
                "name": "Used laptop",
                "description": "Good condition",
                "price": "300000.00",
                "condition": "GOOD",
                "quantity": 1,
                "category": make_category().pk,
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        product = Product.objects.get(pk=created.data["id"])
        self.client.patch(f"/api/products/{product.pk}/", {"status": "ACTIVE"}, format="json")
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.ACTIVE)

        # 3-4. A buyer purchases it (cart + order + paid webhook).
        buyer = make_user("buyer@example.com")
        auth(self.client, buyer)
        self.client.post(
            "/api/cart/items/", {"product_id": product.pk, "quantity": 1}, format="json"
        )
        order_resp = self.client.post("/api/orders/", {"payment_method": "card"}, format="json")
        self.assertEqual(order_resp.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(pk=order_resp.data["id"])
        with patch.object(
            ClickPesaService,
            "initiate_ussd_push",
            return_value={"status": "PROCESSING", "id": "TXN2", "orderReference": "ref2"},
        ):
            self.client.post(
                INITIATE_URL,
                {"order_id": order.pk, "phone_number": "255712345678"},
                format="json",
            )
        payment = Payment.objects.get(order=order)
        self.client.post(
            WEBHOOK_URL,
            signed(
                {
                    "event": "PAYMENT RECEIVED",
                    "data": {
                        "id": "CP2",
                        "status": "SUCCESS",
                        "orderReference": payment.external_reference,
                        "collectedAmount": "300000",
                        "collectedCurrency": "TZS",
                        "message": "ok",
                        "channel": "M-PESA",
                    },
                }
            ),
            format="json",
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

        # 5. Seller sees the incoming order and fulfils it.
        auth(self.client, seller)
        inbox = self.client.get("/api/orders/selling/")
        self.assertEqual(inbox.data["count"], 1)
        item_id = order.items.get().pk
        for action in ("confirm", "ship", "deliver"):
            self.client.post(f"/api/orders/items/{item_id}/{action}/")
        auth(self.client, buyer)
        self.client.post(f"/api/orders/items/{item_id}/complete/")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)

        # 6. See earnings (net of the 6% platform fee) in the wallet.
        auth(self.client, seller)
        earnings = self.client.get("/api/wallet/balance/")
        expected = (Decimal("300000.00") * (Decimal("1") - Decimal("0.06"))).quantize(
            Decimal("0.01")
        )
        self.assertEqual(Decimal(earnings.data["total_earnings"]), expected)

        # 7. Withdraw the available balance.
        withdraw_amount = Decimal(earnings.data["balance"]).quantize(Decimal("0.01"))
        withdraw = self.client.post(
            "/api/withdrawals/",
            {
                "amount": str(withdraw_amount),
                "provider": "mpesa",
                "mobile_money_number": "0712345678",
            },
            format="json",
        )
        self.assertEqual(withdraw.status_code, status.HTTP_201_CREATED, withdraw.data)
        self.assertEqual(withdraw.data["status"], "pending")
