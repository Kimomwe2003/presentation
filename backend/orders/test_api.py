"""API tests for orders (Prompt 05/08)."""

from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from cart.models import Cart
from catalog.test_api import auth, make_category, make_product, make_user
from orders.models import Order, OrderItem

ORDERS_URL = "/api/orders/"


def add_to_cart(client, product, quantity=1):
    return client.post(
        "/api/cart/items/",
        {"product_id": product.pk, "quantity": quantity},
        format="json",
    )


class OrderTests(APITestCase):
    def setUp(self):
        self.seller = make_user("seller@example.com")
        self.user = make_user("buyer@example.com")
        self.category = make_category()
        self.product = make_product(self.seller, self.category, price=Decimal("150.00"))
        auth(self.client, self.user)

    def create_order(self, quantity=2):
        add_to_cart(self.client, self.product, quantity)
        return self.client.post(
            ORDERS_URL,
            {"payment_method": "card", "shipping_cost": "10.00"},
            format="json",
        )

    def test_create_order_requires_auth(self):
        self.client.credentials()
        response = self.client.post(ORDERS_URL, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_order_from_cart(self):
        response = self.create_order()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["subtotal"], "300.00")
        self.assertEqual(response.data["shipping_cost"], "10.00")
        self.assertEqual(response.data["total"], "310.00")
        self.assertEqual(response.data["status"], Order.Status.PENDING_PAYMENT)
        self.assertEqual(len(response.data["items"]), 1)

        order = Order.objects.get(order_number=response.data["order_number"])
        self.assertEqual(order.buyer, self.user)
        self.assertEqual(order.items.first().product_name, "Used laptop")
        self.assertEqual(order.items.first().seller, self.seller)

    def test_cart_flushed_after_order(self):
        self.create_order(quantity=1)
        cart = Cart.objects.get(owner=self.user)
        self.assertEqual(cart.item_count, 0)

    def test_order_list_scoped_to_user(self):
        self.create_order(quantity=1)
        response = self.client.get(ORDERS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

        other = make_user("other@example.com")
        auth(self.client, other)
        response = self.client.get(ORDERS_URL)
        self.assertEqual(response.data["count"], 0)

    def test_anonymous_cart_merged_on_order(self):
        self.client.credentials()
        add_to_cart(self.client, self.product, 1)
        auth(self.client, self.user)
        response = self.client.post(
            ORDERS_URL, {"payment_method": "card"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["items"]), 1)

    def test_order_detail_is_buyer_scoped(self):
        order = self.create_order(quantity=1).data
        response = self.client.get(f"{ORDERS_URL}{order['id']}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], order["id"])

        other = make_user("other@example.com")
        auth(self.client, other)
        response = self.client.get(f"{ORDERS_URL}{order['id']}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_seller_sees_only_own_items_in_selling_detail(self):
        other_seller = make_user("seller2@example.com")
        other_product = make_product(other_seller, self.category, name="Other item")
        add_to_cart(self.client, self.product, 1)
        add_to_cart(self.client, other_product, 1)
        order = self.client.post(
            ORDERS_URL, {"payment_method": "card"}, format="json"
        ).data
        order_id = order["id"]

        auth(self.client, self.seller)
        response = self.client.get(f"{ORDERS_URL}selling/{order_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = response.data["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["product_name"], "Used laptop")

    def test_seller_listing_shows_incoming_orders(self):
        self.create_order(quantity=1)
        auth(self.client, self.seller)
        response = self.client.get(f"{ORDERS_URL}selling/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_seller_listing_filters_by_item_status(self):
        self.create_order(quantity=1)
        auth(self.client, self.seller)

        # No shipped items yet -> empty when filtered to shipped.
        response = self.client.get(f"{ORDERS_URL}selling/", {"item_status": "shipped"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

        order = Order.objects.get(items__seller=self.seller)
        item = order.items.first()
        item.item_status = OrderItem.Status.SHIPPED
        item.save(update_fields=["item_status"])

        response = self.client.get(f"{ORDERS_URL}selling/", {"item_status": "shipped"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], order.pk)

    def test_cancel_pending_order(self):
        order = self.create_order(quantity=1).data
        response = self.client.post(f"{ORDERS_URL}{order['id']}/cancel/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Order.Status.CANCELLED)
        item = Order.objects.get(pk=order["id"]).items.first()
        self.assertEqual(item.item_status, OrderItem.Status.CANCELLED)
