"""Notification tests (Prompt 14).

Covers:
- NotificationService.notify persists a row with the generic relation
- sending a chat message notifies the recipient (never the sender)
- order payment success/failure transitions notify the buyer
- withdrawal status changes notify the requester
- API: list is scoped to the caller; read/read-all/unread-count are secure
"""

from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from catalog.test_api import auth, make_category, make_product, make_user
from chat.services import create_message, get_or_create_conversation
from notifications.models import Notification
from notifications.services import NotificationService
from orders.services import create_order_from_cart, transition_item, transition_order
from orders.state_machine import ACTION_COMPLETE, ACTION_CONFIRM, ACTION_DELIVER
from withdrawals.services import WithdrawalService

NOTIFICATIONS_URL = "/api/notifications/"


class NotificationServiceTests(APITestCase):
    def test_notify_creates_row_with_related_object(self):
        user = make_user("buyer@example.com")
        product = make_product(user)
        notification = NotificationService.notify(
            user=user,
            type_="system",
            title="Hello",
            body="A body",
            related_object=product,
        )
        self.assertIsNotNone(notification)
        self.assertEqual(notification.user, user)
        self.assertEqual(notification.type, "system")
        self.assertFalse(notification.is_read)
        self.assertEqual(notification.related_object, product)

    def test_notify_without_related_object(self):
        user = make_user("buyer@example.com")
        notification = NotificationService.notify(
            user=user, type_="system", title="Hi"
        )
        self.assertIsNone(notification.related_object)
        self.assertIsNone(notification.content_type)


class ChatNotificationTests(APITestCase):
    def setUp(self):
        self.buyer = make_user("buyer@example.com")
        self.seller = make_user("seller@example.com")
        self.product = make_product(self.seller)
        self.conv, _ = get_or_create_conversation(user=self.buyer, product=self.product)

    def test_message_notifies_recipient_not_sender(self):
        create_message(conversation=self.conv, sender=self.seller, body="Hello buyer")
        recipient_notif = Notification.objects.filter(
            user=self.buyer, type="new_message"
        )
        self.assertEqual(recipient_notif.count(), 1)
        self.assertFalse(
            Notification.objects.filter(user=self.seller, type="new_message").exists()
        )

    def test_sender_never_notified(self):
        create_message(conversation=self.conv, sender=self.buyer, body="Hi there")
        # The seller is the recipient here, so they ARE notified; the buyer
        # (sender) must never receive their own message notification.
        self.assertEqual(
            Notification.objects.filter(user=self.seller, type="new_message").count(), 1
        )
        self.assertEqual(
            Notification.objects.filter(user=self.buyer, type="new_message").count(), 0
        )


class OrderNotificationTests(APITestCase):
    def setUp(self):
        self.seller = make_user("seller@example.com")
        self.buyer = make_user("buyer@example.com")
        self.category = make_category()
        self.product = make_product(
            self.seller, self.category, price=Decimal("100.00")
        )
        from cart.models import Cart, CartItem

        cart = Cart.objects.create(owner=self.buyer)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        self.order = create_order_from_cart(
            user=self.buyer,
            cart=cart,
            payment_method="card",
            shipping_address="Street 1",
        )

    def test_payment_success_notifies_buyer(self):
        transition_order(self.order, "mark_paid", actor="payment")
        self.assertTrue(
            Notification.objects.filter(
                user=self.buyer, type="payment_result"
            ).exists()
        )

    def test_payment_failure_notifies_buyer(self):
        transition_order(self.order, "fail_payment", actor="payment")
        self.assertTrue(
            Notification.objects.filter(
                user=self.buyer, type="payment_result"
            ).exists()
        )

    def test_seller_fulfillment_notifies_buyer(self):
        transition_order(self.order, "mark_paid", actor="payment")
        item = self.order.items.get()
        from orders.state_machine import ACTION_SHIP

        for action in (ACTION_CONFIRM, ACTION_SHIP, ACTION_DELIVER):
            transition_item(item, action, user=self.seller, actor="seller")
        self.assertEqual(
            Notification.objects.filter(
                user=self.buyer, type="order_update"
            ).count(), 3
        )

    def test_buyer_completion_notifies_seller(self):
        transition_order(self.order, "mark_paid", actor="payment")
        item = self.order.items.get()
        from orders.state_machine import ACTION_SHIP

        for action in (ACTION_CONFIRM, ACTION_SHIP, ACTION_DELIVER):
            transition_item(item, action, user=self.seller, actor="seller")
        transition_item(item, ACTION_COMPLETE, user=self.buyer, actor="buyer")
        self.assertTrue(
            Notification.objects.filter(
                user=self.seller, type="order_update"
            ).exists()
        )


class WithdrawalNotificationTests(APITestCase):
    def setUp(self):
        self.user = make_user("buyer@example.com")
        from wallet.services import WalletService

        WalletService.credit(
            self.user, Decimal("10000.00"), reference="seed", description="Test credit"
        )
        self.request = WithdrawalService.request_withdrawal(
            self.user,
            amount=Decimal("5000.00"),
            provider="vodacom",
            mobile_money_number="+255700000000",
        )
        self.admin = make_user("admin@example.com")
        self.admin.is_staff = True
        self.admin.save()

    def test_transition_notifies_requester(self):
        WithdrawalService.process(self.request, actor=self.admin)
        WithdrawalService.complete(self.request, actor=self.admin)
        self.assertTrue(
            Notification.objects.filter(
                user=self.user, type="withdrawal_update"
            ).exists()
        )

    def test_rejection_notifies_requester(self):
        WithdrawalService.reject(self.request, actor=self.admin)
        self.assertTrue(
            Notification.objects.filter(
                user=self.user, type="withdrawal_update"
            ).exists()
        )


class NotificationApiTests(APITestCase):
    def setUp(self):
        self.user = make_user("buyer@example.com")
        self.other = make_user("other@example.com")
        NotificationService.notify(user=self.user, type_="system", title="A")
        NotificationService.notify(user=self.user, type_="system", title="B")
        NotificationService.notify(user=self.other, type_="system", title="Hidden")
        auth(self.client, self.user)

    def test_requires_auth(self):
        anon = self.client_class()
        response = anon.get(NOTIFICATIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_scoped_to_caller(self):
        response = self.client.get(NOTIFICATIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["B", "A"])
        self.assertNotIn("Hidden", titles)

    def test_unread_count(self):
        response = self.client.get(f"{NOTIFICATIONS_URL}unread-count/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["unread_count"], 2)

    def test_mark_one_read(self):
        notification = Notification.objects.get(user=self.user, title="A")
        response = self.client.post(f"{NOTIFICATIONS_URL}{notification.pk}/read/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_cannot_mark_other_users_notification(self):
        hidden = Notification.objects.get(user=self.other)
        response = self.client.post(f"{NOTIFICATIONS_URL}{hidden.pk}/read/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_read_all(self):
        response = self.client.post(f"{NOTIFICATIONS_URL}read-all/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["marked_read"], 2)
        self.assertFalse(
            Notification.objects.filter(user=self.user, is_read=False).exists()
        )

    def test_read_all_ignores_others(self):
        self.client.post(f"{NOTIFICATIONS_URL}read-all/")
        self.assertFalse(
            Notification.objects.filter(user=self.other, is_read=True).exists()
        )
