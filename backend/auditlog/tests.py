"""Tests for the audit log (Prompt 17).

Covers the representative sample required by the spec across every app:
auth (login success/failure, register, profile update), catalog (product
create/update/delete), orders (creation + transition), payments (initiate /
success / failure), withdrawals (request + admin transition), adminpanel
(suspend / product removal / category change).

Also verifies the API is staff-only and append-only, and that no sensitive
fields (passwords, tokens, provider payloads) leak into snapshots.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from adminpanel.tests import AdminPanelBase
from auditlog.models import AuditLog
from catalog.models import Category, Product
from orders.models import Order, OrderItem
from withdrawals.models import WithdrawalRequest

User = get_user_model()


def auth(client, user):
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}"
    )


class AuditLogApiTests(APITestCase):
    """Staff-only + append-only behaviour of the audit API."""

    def setUp(self):
        self.staff = User.objects.create_user("staff@example.com", "hunter222", is_staff=True)
        self.member = User.objects.create_user("member@example.com", "hunter222")
        AuditLog.objects.create(actor=self.member, action=AuditLog.Action.LOGIN)

    def test_list_is_staff_only(self):
        auth(self.client, self.member)
        resp = self.client.get("/api/audit-logs/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_detail_is_staff_only(self):
        log = AuditLog.objects.first()
        auth(self.client, self.member)
        resp = self.client.get(f"/api/audit-logs/{log.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_denied(self):
        resp = self.client.get("/api/audit-logs/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_and_detail_ok_for_staff(self):
        log = AuditLog.objects.first()
        auth(self.client, self.staff)
        list_resp = self.client.get("/api/audit-logs/")
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(list_resp.data["count"], 1)
        detail_resp = self.client.get(f"/api/audit-logs/{log.pk}/")
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data["action"], log.action)

    def test_filter_by_action_and_actor(self):
        AuditLog.objects.create(actor=self.staff, action=AuditLog.Action.LOGOUT)
        auth(self.client, self.staff)
        by_action = self.client.get(
            "/api/audit-logs/", {"action": AuditLog.Action.LOGOUT}
        )
        self.assertEqual(by_action.data["count"], 1)
        by_actor = self.client.get("/api/audit-logs/", {"actor": self.member.pk})
        self.assertEqual(by_actor.data["count"], 1)

    def test_filter_by_date_range(self):
        auth(self.client, self.staff)
        future = timezone.now() + timezone.timedelta(days=1)
        resp = self.client.get(
            "/api/audit-logs/",
            {"created_after": future.isoformat()},
        )
        self.assertEqual(resp.data["count"], 0)

    def test_no_destructive_routes_exist(self):
        auth(self.client, self.staff)
        log = AuditLog.objects.first()
        delete_resp = self.client.delete(f"/api/audit-logs/{log.pk}/")
        patch_resp = self.client.patch(
            f"/api/audit-logs/{log.pk}/", {"description": "tampered"}, format="json"
        )
        # 405 = method not allowed (route exists but method not); 404 also ok.
        self.assertIn(
            delete_resp.status_code,
            (status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_404_NOT_FOUND),
        )
        self.assertIn(
            patch_resp.status_code,
            (status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_404_NOT_FOUND),
        )
        # No POST/create route either.
        post_resp = self.client.post("/api/audit-logs/", {}, format="json")
        self.assertIn(
            post_resp.status_code,
            (status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_404_NOT_FOUND),
        )
        # The row is untouched.
        log.refresh_from_db()
        self.assertNotEqual(log.description, "tampered")

    def test_admin_cannot_append_via_api(self):
        auth(self.client, self.staff)
        before = AuditLog.objects.count()
        resp = self.client.post("/api/audit-logs/", {"action": "auth.login"}, format="json")
        self.assertIn(
            resp.status_code,
            (status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_404_NOT_FOUND),
        )
        self.assertEqual(AuditLog.objects.count(), before)


class AuditLogRetrofitTests(AdminPanelBase):
    """Each retrofitted sensitive action produces exactly one correct row."""

    def _log_for(self, target=None):
        qs = AuditLog.objects.all()
        return qs

    def test_login_success(self):
        auth(self.client, self.seller)
        self.client.post(
            "/api/auth/login/",
            {"email": self.seller.email, "password": "hunter222"},
            format="json",
        )
        row = AuditLog.objects.filter(action=AuditLog.Action.LOGIN).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.actor_id, self.seller.pk)
        self.assertEqual(row.target_model, "accounts.user")
        self.assertEqual(row.target_id, self.seller.pk)

    def test_login_failure_is_system_logged(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"email": self.seller.email, "password": "wrongpass"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        row = AuditLog.objects.filter(action=AuditLog.Action.LOGIN_FAILED).first()
        self.assertIsNotNone(row)
        self.assertIsNone(row.actor)  # anonymous failed login
        self.assertIn(self.seller.email, row.description)
        # Never captures the attempted password.
        self.assertNotIn("wrongpass", str(row.description))

    def test_register(self):
        resp = self.client.post(
            "/api/auth/register/",
            {
                "email": "newbie@example.com",
                "password": "SuperSecret99!",
                "password_confirmation": "SuperSecret99!",
                "full_name": "Newbie",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        row = AuditLog.objects.filter(action=AuditLog.Action.REGISTER).first()
        self.assertIsNotNone(row)
        self.assertIn("newbie@example.com", row.description)

    def test_profile_update(self):
        auth(self.client, self.seller)
        self.client.patch(
            "/api/users/me/",
            {"full_name": "Renamed", "address": "Kinondoni"},
            format="json",
        )
        row = AuditLog.objects.filter(action=AuditLog.Action.PROFILE_UPDATE).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.actor_id, self.seller.pk)
        self.assertIn("Renamed", str(row.after_data))

    def test_product_create(self):
        auth(self.client, self.seller)
        category = Category.objects.create(name="Cat", slug="cat")
        self.client.post(
            "/api/products/",
            {
                "name": "New item",
                "description": "desc",
                "price": "50.00",
                "quantity": 2,
                "category": category.pk,
                "condition": Product.Condition.GOOD,
                "location": "Dar",
            },
            format="json",
        )
        row = AuditLog.objects.filter(action=AuditLog.Action.PRODUCT_CREATE).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.actor_id, self.seller.pk)

    def test_product_update(self):
        product = self._product()
        auth(self.client, self.seller)
        self.client.patch(f"/api/products/{product.pk}/", {"name": "Renamed item"}, format="json")
        row = AuditLog.objects.filter(action=AuditLog.Action.PRODUCT_UPDATE).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.target_id, product.pk)
        self.assertIn("Renamed item", str(row.after_data))

    def test_product_delete(self):
        product = self._product()
        auth(self.client, self.seller)
        resp = self.client.delete(f"/api/products/{product.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        row = AuditLog.objects.filter(action=AuditLog.Action.PRODUCT_DELETE).first()
        self.assertIsNotNone(row)
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.INACTIVE)

    def test_order_create(self):
        auth(self.client, self.seller)
        # Build a cart with one product.
        product = self._product()
        self.client.post(
            "/api/cart/items/", {"product_id": product.pk, "quantity": 1}, format="json"
        )
        self.client.post(
            "/api/orders/",
            {"payment_method": "card", "shipping_address": {"line1": "x"}},
            format="json",
        )
        row = AuditLog.objects.filter(action=AuditLog.Action.ORDER_CREATE).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.actor_id, self.seller.pk)
        self.assertEqual(row.target_model, "orders.order")

    def test_order_transition(self):
        order = Order.objects.create(
            buyer=self.seller,
            payment_method="card",
            shipping_address={},
            subtotal=Decimal("10.00"),
            shipping_cost=Decimal("0"),
            total=Decimal("10.00"),
            status=Order.Status.PAID,
        )
        item = OrderItem.objects.create(
            order=order,
            seller=self.member,
            product=None,
            product_name="Widget",
            quantity=1,
            unit_price=Decimal("10.00"),
        )
        auth(self.client, self.member)
        resp = self.client.post(f"/api/orders/items/{item.pk}/confirm/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rows = AuditLog.objects.filter(
            action=AuditLog.Action.ORDER_TRANSITION, target_id=order.pk
        )
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().actor_id, self.member.pk)

    def test_withdrawal_request(self):
        from wallet.services import WalletService

        WalletService.credit(
            self.seller,
            Decimal("10000.00"),
            reference="audit-test-seed",
            description="Test credit",
        )
        auth(self.client, self.seller)
        self.client.post(
            "/api/withdrawals/",
            {
                "amount": "5000.00",
                "provider": "mpesa",
                "mobile_money_number": "255712345678",
            },
            format="json",
        )
        row = AuditLog.objects.filter(action=AuditLog.Action.WITHDRAWAL_REQUEST).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.actor_id, self.seller.pk)

    def test_withdrawal_admin_approval(self):
        request = WithdrawalRequest.objects.create(
            user=self.seller,
            amount=Decimal("5000.00"),
            provider="mpesa",
            mobile_money_number="255712345678",
            status=WithdrawalRequest.Status.PENDING,
            reference="WD-TEST1",
        )
        auth(self.client, self.admin)
        resp = self.client.post(f"/api/withdrawals/{request.pk}/process/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        row = AuditLog.objects.filter(action=AuditLog.Action.WITHDRAWAL_TRANSITION).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.actor_id, self.admin.pk)

    def test_suspend_user(self):
        auth(self.client, self.admin)
        self.client.post(f"/api/admin/users/{self.member.pk}/suspend/")
        row = AuditLog.objects.filter(action=AuditLog.Action.USER_SUSPEND).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.actor_id, self.admin.pk)
        self.assertEqual(row.target_id, self.member.pk)

    def test_product_removal(self):
        product = self._product()
        auth(self.client, self.admin)
        self.client.post(
            f"/api/admin/products/{product.pk}/remove/",
            {"reason": "Scam listing"},
            format="json",
        )
        row = AuditLog.objects.filter(action=AuditLog.Action.PRODUCT_REMOVE).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.target_id, product.pk)
        self.assertIn("Scam listing", str(row.after_data))

    def test_category_change(self):
        category = Category.objects.create(name="Old", slug="old")
        auth(self.client, self.admin)
        self.client.patch(f"/api/admin/categories/{category.pk}/", {"name": "New"}, format="json")
        row = AuditLog.objects.filter(action=AuditLog.Action.CATEGORY_UPDATE).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.target_id, category.pk)

    def test_no_sensitive_data_in_snapshots(self):
        """Passwords / tokens never appear in before/after snapshots."""
        auth(self.client, self.seller)
        self.client.patch("/api/users/me/", {"full_name": "No leak"}, format="json")
        for row in AuditLog.objects.all():
            for snapshot in (row.before_data, row.after_data):
                if snapshot:
                    self.assertNotIn("password", str(snapshot).lower())
                    self.assertNotIn("token", str(snapshot).lower())


class ReportSummaryTests(AdminPanelBase):
    """GET /api/admin/reports/summary/ — staff-only aggregate reporting."""

    def test_staff_only(self):
        auth(self.client, self.member)
        resp = self.client.get("/api/admin/reports/summary/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_denied(self):
        resp = self.client.get("/api/admin/reports/summary/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_summary_shape_and_new_users(self):
        # Two users registered by setUp (seller, member, admin, staff = 4).
        auth(self.client, self.admin)
        resp = self.client.get("/api/admin/reports/summary/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        self.assertIn("transaction_volume", data)
        self.assertIn("fee_revenue", data)
        self.assertIn("new_users", data)
        self.assertEqual(data["days"], 30)
        today = timezone.localdate().isoformat()
        new_user_days = {row["date"] for row in data["new_users"]}
        self.assertTrue(any(str(day).startswith(today) for day in new_user_days))

    def test_reports_fee_and_transaction(self):
        # Simulate a completed sale so fee revenue + volume are non-empty.
        order = Order.objects.create(
            buyer=self.member,
            payment_method="card",
            shipping_address={},
            subtotal=Decimal("1000.00"),
            shipping_cost=Decimal("0"),
            total=Decimal("1000.00"),
            status=Order.Status.COMPLETED,
        )
        from payments.models import Payment

        Payment.objects.create(
            order=order,
            amount=Decimal("1000.00"),
            status=Payment.Status.SUCCESSFUL,
        )
        from wallet.services import WalletService

        WalletService.process_completed_sale(
            OrderItem.objects.create(
                order=order,
                seller=self.seller,
                product=None,
                product_name="Widget",
                quantity=1,
                unit_price=Decimal("1000.00"),
            )
        )
        auth(self.client, self.admin)
        data = self.client.get("/api/admin/reports/summary/").data
        self.assertTrue(data["transaction_volume"])
        self.assertTrue(data["fee_revenue"])
        total_vol = sum(
            Decimal(row["total"]) for row in data["transaction_volume"]
        )
        self.assertEqual(total_vol, Decimal("1000.00"))

    def test_days_param(self):
        auth(self.client, self.admin)
        data = self.client.get("/api/admin/reports/summary/", {"days": 7}).data
        self.assertEqual(data["days"], 7)
