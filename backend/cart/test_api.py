"""API tests for the cart (Prompt 05)."""

from rest_framework import status
from rest_framework.test import APITestCase

from cart.models import Cart
from catalog.models import Product
from catalog.test_api import auth, make_category, make_product, make_user

CART_URL = "/api/cart/"
ITEMS_URL = "/api/cart/items/"


class AnonymousCartTests(APITestCase):
    def setUp(self):
        self.seller = make_user()
        self.product = make_product(self.seller, make_category())

    def test_get_cart_creates_anonymous_cart(self):
        response = self.client.get(CART_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["item_count"], 0)
        self.assertIn("items", response.data)
        self.assertIn("subtotal_pretty", response.data)

    def test_add_item_to_anonymous_cart(self):
        response = self.client.post(
            ITEMS_URL, {"product_id": str(self.product.pk), "quantity": 2}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["product_id"], self.product.pk)
        self.assertEqual(response.data["product_name"], self.product.name)
        self.assertIn("product_image", response.data)
        self.assertEqual(response.data["condition"], self.product.condition)
        self.assertEqual(response.data["quantity"], 2)
        self.assertEqual(response.data["total"], "300.00")

        cart = self.client.get(CART_URL)
        self.assertEqual(cart.data["item_count"], 2)
        self.assertEqual(cart.data["subtotal"], "300.00")

    def test_cart_persists_across_requests_via_session(self):
        self.client.post(
            ITEMS_URL, {"product_id": str(self.product.pk), "quantity": 1}, format="json"
        )
        response = self.client.get(CART_URL)
        self.assertEqual(response.data["item_count"], 1)

    def test_invalid_product_rejected(self):
        response = self.client.post(
            ITEMS_URL,
            {"product_id": 999999, "quantity": 1},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_quantity_validation(self):
        response = self.client.post(
            ITEMS_URL, {"product_id": str(self.product.pk), "quantity": 0}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AuthenticatedCartTests(APITestCase):
    def setUp(self):
        self.seller = make_user("seller@example.com")
        self.user = make_user("buyer@example.com")
        self.category = make_category()
        self.product = make_product(self.seller, self.category)
        auth(self.client, self.user)

    def test_authenticated_cart_tied_to_user(self):
        self.client.post(
            ITEMS_URL, {"product_id": str(self.product.pk), "quantity": 1}, format="json"
        )
        cart = Cart.objects.get(owner=self.user)
        self.assertEqual(cart.item_count, 1)

    def test_update_item_quantity(self):
        item = self.client.post(
            ITEMS_URL, {"product_id": str(self.product.pk), "quantity": 1}, format="json"
        ).data
        response = self.client.patch(
            f"{ITEMS_URL}{item['id']}/", {"quantity": 5}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["quantity"], 5)

    def test_remove_item(self):
        item = self.client.post(
            ITEMS_URL, {"product_id": str(self.product.pk), "quantity": 1}, format="json"
        ).data
        response = self.client.delete(f"{ITEMS_URL}{item['id']}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        cart = self.client.get(CART_URL)
        self.assertEqual(cart.data["item_count"], 0)

    def test_cannot_modify_another_users_item(self):
        other = make_user("other@example.com")
        auth(self.client, other)
        self.client.post(
            ITEMS_URL, {"product_id": str(self.product.pk), "quantity": 1}, format="json"
        )
        other_item = self.client.get(ITEMS_URL).data[0]["id"]

        auth(self.client, self.user)
        response = self.client.delete(f"{ITEMS_URL}{other_item}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_draft_product_not_available(self):
        draft = make_product(self.seller, self.category, status=Product.Status.DRAFT)
        response = self.client.post(
            ITEMS_URL, {"product_id": str(draft.pk), "quantity": 1}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
