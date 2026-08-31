"""Review tests (Prompt 15).

Covers the completed-purchase restriction (positive + negative cases),
one-review-per-order-item, rating bounds (1-5), and server-side aggregation
math on product + seller profiles.
"""

from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from catalog.test_api import auth, make_category, make_product, make_user
from orders.models import OrderItem
from orders.services import create_order_from_cart, transition_item, transition_order
from orders.state_machine import (
    ACTION_COMPLETE,
    ACTION_CONFIRM,
    ACTION_DELIVER,
    ACTION_MARK_PAID,
    ACTION_SHIP,
)
from reviews.models import Review

REVIEWS_URL = "/api/reviews/"


def complete_order_item(item: OrderItem):
    """Drive an order item to COMPLETED through the sanctioned state machine."""
    transition_order(item.order, ACTION_MARK_PAID, actor="payment")
    item.refresh_from_db()
    for action in (ACTION_CONFIRM, ACTION_SHIP, ACTION_DELIVER):
        transition_item(item, action, user=item.seller, actor="seller")
    transition_item(item, ACTION_COMPLETE, user=item.order.buyer, actor="buyer")


class ReviewFixture(APITestCase):
    def setUp(self):
        self.seller = make_user("seller@example.com")
        self.buyer = make_user("buyer@example.com")
        self.category = make_category()
        self.product = make_product(
            self.seller, self.category, price=Decimal("100.00")
        )
        self.order = self._create_purchased_order(self.buyer, self.product)
        self.item = self.order.items.get()

    def _cart_for(self, user):
        from cart.models import Cart

        return Cart.objects.get_or_create(owner=user)[0]

    def _create_purchased_order(self, user, product):
        from cart.models import CartItem

        cart = self._cart_for(user)
        cart.items.all().delete()
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        return create_order_from_cart(
            user=user,
            cart=cart,
            payment_method="card",
            shipping_address="Street 1",
        )

    def review_payload(self, **overrides):
        payload = {"order_item_id": self.item.pk, "rating": 5, "comment": "Great!"}
        payload.update(overrides)
        return payload


class ReviewCreationTests(ReviewFixture):
    def test_review_requires_auth(self):
        self.client.credentials()
        response = self.client.post(REVIEWS_URL, self.review_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cannot_review_without_completed_purchase(self):
        # Item is still PENDING.
        auth(self.client, self.buyer)
        response = self.client.post(REVIEWS_URL, self.review_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 0)

    def test_cannot_review_an_item_you_did_not_buy(self):
        complete_order_item(self.item)
        stranger = make_user("stranger@example.com")
        auth(self.client, stranger)
        response = self.client.post(REVIEWS_URL, self.review_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 0)

    def test_cannot_review_a_product_you_never_purchased(self):
        # Attacker holds no order for this product at all. The item belongs to
        # the buyer's completed order; the attacker is not its buyer -> blocked.
        complete_order_item(self.item)
        attacker = make_user("attacker@example.com")
        auth(self.client, attacker)
        response = self.client.post(
            REVIEWS_URL,
            {"order_item_id": self.item.pk, "rating": 4, "comment": "x"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 0)

    def test_review_after_completed_purchase_succeeds(self):
        complete_order_item(self.item)
        auth(self.client, self.buyer)
        response = self.client.post(REVIEWS_URL, self.review_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        review = Review.objects.get()
        self.assertEqual(review.buyer, self.buyer)
        self.assertEqual(review.product, self.product)
        self.assertEqual(review.order_item, self.item)
        self.assertEqual(review.rating, 5)
        # product is derived server-side from the order item.
        self.assertEqual(response.data["product"], self.product.pk)

    def test_cannot_double_review_same_order_item(self):
        complete_order_item(self.item)
        auth(self.client, self.buyer)
        first = self.client.post(REVIEWS_URL, self.review_payload(), format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(
            REVIEWS_URL,
            self.review_payload(rating=3, comment="second try"),
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 1)

    def test_rating_bounds_enforced(self):
        complete_order_item(self.item)
        auth(self.client, self.buyer)
        for bad in (0, 6, -1):
            response = self.client.post(
                REVIEWS_URL, self.review_payload(rating=bad), format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 0)


class ReviewListTests(ReviewFixture):
    def setUp(self):
        super().setUp()
        complete_order_item(self.item)
        self.buyer2 = make_user("buyer2@example.com")
        # A second completed purchase by another buyer for aggregation.
        order2 = self._create_purchased_order(self.buyer2, self.product)
        self.item2 = order2.items.get()
        complete_order_item(self.item2)

        Review.objects.create(
            order_item=self.item, buyer=self.buyer, product=self.product, rating=5, comment="A"
        )
        Review.objects.create(
            order_item=self.item2, buyer=self.buyer2, product=self.product, rating=4, comment="B"
        )

    def test_list_by_product_returns_all(self):
        response = self.client.get(f"{REVIEWS_URL}product/{self.product.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        ratings = {r["rating"] for r in response.data["results"]}
        self.assertEqual(ratings, {4, 5})

    def test_list_by_seller_returns_reviews_of_sellers_products(self):
        response = self.client.get(f"{REVIEWS_URL}seller/{self.seller.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["rating_count"], 2)
        self.assertEqual(response.data["average_rating"], 4.5)
        self.assertEqual(response.data["reviews"]["count"], 2)
        self.assertEqual(response.data["seller"]["id"], self.seller.pk)


class RatingAggregationTests(ReviewFixture):
    def setUp(self):
        super().setUp()
        self.buyer2 = make_user("buyer2@example.com")

    def _create_completed_review(self, user, rating):
        order = self._create_purchased_order(user, self.product)
        item = order.items.get()
        complete_order_item(item)
        Review.objects.create(
            order_item=item, buyer=user, product=self.product, rating=rating
        )
        return item

    def test_product_detail_has_server_computed_rating(self):
        self._create_completed_review(self.buyer, 5)
        self._create_completed_review(self.buyer2, 3)
        auth(self.client, self.buyer)
        response = self.client.get(f"/api/products/{self.product.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["average_rating"], 4.0)
        self.assertEqual(response.data["rating_count"], 2)
        # Seller mini-profile also carries aggregation.
        self.assertEqual(response.data["seller"]["average_rating"], 4.0)
        self.assertEqual(response.data["seller"]["rating_count"], 2)

    def test_product_with_no_reviews_has_null_rating(self):
        response = self.client.get(f"/api/products/{self.product.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["average_rating"])
        self.assertEqual(response.data["rating_count"], 0)

    def test_seller_average_math_across_products(self):
        # Ratings 5 and 3 on one product; add 2 on a second product -> avg 3.33.
        self._create_completed_review(self.buyer, 5)
        self._create_completed_review(self.buyer2, 3)
        second = make_product(self.seller, self.category, name="Second", price="50.00")
        order = self._create_purchased_order(self.buyer, second)
        item = order.items.get()
        complete_order_item(item)
        Review.objects.create(
            order_item=item, buyer=self.buyer, product=second, rating=2
        )
        response = self.client.get(f"{REVIEWS_URL}seller/{self.seller.pk}/")
        self.assertEqual(response.data["rating_count"], 3)
        self.assertEqual(response.data["average_rating"], round(10 / 3, 1))
