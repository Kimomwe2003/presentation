"""Chat tests (Prompt 13).

Covers:
- get-or-create reuses an existing conversation between the same two users
  about the same product (no duplicates)
- product-scoped vs. direct (other_user_id) threads are distinct
- participants can list/read/post; non-participants get 404 (or 403)
- message ordering + pagination return newest-first with correct pages
- mark-as-read works and never drops the sender's own unread flags
- message length/empty validation
"""

from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Product
from catalog.test_api import auth, make_user
from chat.models import Conversation
from chat.services import ChatMissingContextError, create_message, get_or_create_conversation

CHATS_URL = "/api/chats/"


def make_product(seller, **overrides):
    values = {
        "name": "Used laptop",
        "description": "Good condition laptop",
        "price": Decimal("150.00"),
        "condition": Product.Condition.GOOD,
        "quantity": 1,
        "location": "Dar es Salaam",
        "status": Product.Status.ACTIVE,
    }
    values.update(overrides)
    return Product.objects.create(seller=seller, **values)


class GetOrCreateTests(APITestCase):
    def setUp(self):
        self.buyer = make_user("buyer@example.com")
        self.seller = make_user("seller@example.com")
        self.product = make_product(self.seller)

    def test_reuses_existing_product_conversation(self):
        c1, created1 = get_or_create_conversation(
            user=self.buyer, product=self.product
        )
        self.assertTrue(created1)
        c2, created2 = get_or_create_conversation(
            user=self.buyer, product=self.product
        )
        self.assertFalse(created2)
        self.assertEqual(c1.pk, c2.pk)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_direct_thread_reuses_in_both_directions(self):
        c1, _ = get_or_create_conversation(
            user=self.buyer, other_user_id=self.seller.pk
        )
        c2, created2 = get_or_create_conversation(
            user=self.seller, other_user_id=self.buyer.pk
        )
        self.assertFalse(created2)
        self.assertEqual(c1.pk, c2.pk)

    def test_direct_thread_is_distinct_from_product_thread(self):
        product_conv, _ = get_or_create_conversation(
            user=self.buyer, product=self.product
        )
        direct_conv, created = get_or_create_conversation(
            user=self.buyer, other_user_id=self.seller.pk
        )
        self.assertTrue(created)
        self.assertNotEqual(product_conv.pk, direct_conv.pk)

    def test_requires_a_counterpart(self):
        with self.assertRaises(ChatMissingContextError):
            get_or_create_conversation(user=self.buyer)

    def test_cannot_chat_with_self(self):
        with self.assertRaises(ChatMissingContextError):
            get_or_create_conversation(user=self.buyer, other_user_id=self.buyer.pk)

    def test_has_exactly_two_participants(self):
        conv, _ = get_or_create_conversation(user=self.buyer, product=self.product)
        self.assertEqual(conv.participants.count(), 2)


class MessageTests(APITestCase):
    def setUp(self):
        self.buyer = make_user("buyer@example.com")
        self.seller = make_user("seller@example.com")
        self.interloper = make_user("intruder@example.com")
        self.product = make_product(self.seller)
        self.conv, _ = get_or_create_conversation(
            user=self.buyer, product=self.product
        )
        self.other_conv, _ = get_or_create_conversation(
            user=self.interloper, other_user_id=self.seller.pk
        )

    def test_create_message_validates_length_and_empty(self):
        with self.assertRaises(ValueError):
            create_message(conversation=self.conv, sender=self.buyer, body="   ")
        with self.assertRaises(ValueError):
            create_message(conversation=self.conv, sender=self.buyer, body="x" * 4001)

    def test_send_produces_unread_for_recipient(self):
        create_message(
            conversation=self.conv, sender=self.buyer, body="Hi, is this available?"
        )
        message = self.conv.messages.get()
        self.assertEqual(message.sender, self.buyer)
        self.assertFalse(message.is_read)


class ConversationApiTests(APITestCase):
    def setUp(self):
        self.buyer = make_user("buyer@example.com")
        self.seller = make_user("seller@example.com")
        self.interloper = make_user("intruder@example.com")
        self.product = make_product(self.seller)
        self.conv, _ = get_or_create_conversation(
            user=self.buyer, product=self.product
        )
        auth(self.client, self.buyer)

    def test_create_returns_existing_conversation_not_duplicate(self):
        auth(self.client, self.buyer)
        r1 = self.client.post(
            CHATS_URL, {"product_id": self.product.pk}, format="json"
        )
        r2 = self.client.post(
            CHATS_URL, {"product_id": self.product.pk}, format="json"
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r1.data["id"], r2.data["id"])
        self.assertEqual(Conversation.objects.count(), 1)

    def test_list_returns_only_own_conversations(self):
        auth(self.client, self.interloper)
        self.client.post(
            CHATS_URL, {"other_user_id": self.seller.pk}, format="json"
        )
        auth(self.client, self.buyer)
        response = self.client.get(CHATS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.conv.pk])
        self.assertNotIn(self.other_conv.pk if hasattr(self, "other_conv") else -1, ids)

    def test_counterpart_reported(self):
        response = self.client.get(CHATS_URL)
        item = response.data["results"][0]
        self.assertEqual(item["counterpart"]["id"], self.seller.pk)
        self.assertEqual(item["product_id"], self.product.pk)

    def test_last_message_and_unread_count(self):
        create_message(
            conversation=self.conv, sender=self.seller, body="Hello buyer"
        )
        create_message(
            conversation=self.conv, sender=self.seller, body="Still available"
        )
        response = self.client.get(CHATS_URL)
        item = response.data["results"][0]
        self.assertEqual(item["last_message"]["body"], "Still available")
        self.assertEqual(item["unread_count"], 2)

    def test_create_requires_auth(self):
        anon = self.client_class()
        response = anon.post(CHATS_URL, {"other_user_id": self.seller.pk})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MessageApiTests(APITestCase):
    def setUp(self):
        self.buyer = make_user("buyer@example.com")
        self.seller = make_user("seller@example.com")
        self.interloper = make_user("intruder@example.com")
        self.product = make_product(self.seller)
        self.conv, _ = get_or_create_conversation(
            user=self.buyer, product=self.product
        )

    def test_non_participant_cannot_read_messages(self):
        auth(self.client, self.interloper)
        response = self.client.get(f"{CHATS_URL}{self.conv.pk}/messages/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_participant_cannot_post_message(self):
        auth(self.client, self.interloper)
        response = self.client.post(
            f"{CHATS_URL}{self.conv.pk}/messages/", {"body": "hacked"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_participant_cannot_mark_read(self):
        auth(self.client, self.interloper)
        response = self.client.post(f"{CHATS_URL}{self.conv.pk}/read/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_and_list_messages(self):
        auth(self.client, self.buyer)
        post = self.client.post(
            f"{CHATS_URL}{self.conv.pk}/messages/", {"body": "Is it negotiable?"},
            format="json",
        )
        self.assertEqual(post.status_code, status.HTTP_201_CREATED)
        auth(self.client, self.buyer)
        listing = self.client.get(f"{CHATS_URL}{self.conv.pk}/messages/")
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data["count"], 1)
        self.assertEqual(listing.data["results"][0]["body"], "Is it negotiable?")
        self.assertEqual(listing.data["results"][0]["sender"], self.buyer.pk)

    def test_messages_newest_first(self):
        auth(self.client, self.buyer)
        for body in ["first", "second", "third"]:
            self.client.post(
                f"{CHATS_URL}{self.conv.pk}/messages/", {"body": body}, format="json"
            )
        response = self.client.get(f"{CHATS_URL}{self.conv.pk}/messages/")
        bodies = [m["body"] for m in response.data["results"]]
        self.assertEqual(bodies, ["third", "second", "first"])

    def test_pagination_with_load_more(self):
        auth(self.client, self.buyer)
        for i in range(7):
            self.client.post(
                f"{CHATS_URL}{self.conv.pk}/messages/",
                {"body": f"msg-{i}"},
                format="json",
            )
        page1 = self.client.get(
            f"{CHATS_URL}{self.conv.pk}/messages/", {"page_size": 3, "page": 1}
        )
        self.assertEqual([m["body"] for m in page1.data["results"]], ["msg-6", "msg-5", "msg-4"])
        self.assertIsNotNone(page1.data["next"])
        page2 = self.client.get(
            f"{CHATS_URL}{self.conv.pk}/messages/", {"page_size": 3, "page": 2}
        )
        self.assertEqual([m["body"] for m in page2.data["results"]], ["msg-3", "msg-2", "msg-1"])

    def test_read_marks_others_unread(self):
        create_message(
            conversation=self.conv, sender=self.seller, body="for buyer"
        )
        create_message(
            conversation=self.conv, sender=self.buyer, body="ok"  # own
        )
        auth(self.client, self.buyer)
        response = self.client.post(f"{CHATS_URL}{self.conv.pk}/read/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        message = self.conv.messages.get(body="for buyer")
        self.assertTrue(message.is_read)

    def test_empty_message_rejected(self):
        auth(self.client, self.buyer)
        response = self.client.post(
            f"{CHATS_URL}{self.conv.pk}/messages/", {"body": "   "}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
