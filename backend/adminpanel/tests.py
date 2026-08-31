"""Tests for the adminpanel dashboard & moderation API (Prompt 16)."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile
from catalog.models import Category, Product

User = get_user_model()


class AdminPanelBase(APITestCase):
    def setUp(self):
        self.seller = self._make_user(
            "seller@example.com",
            full_name="Seller Person",
            account_status=Profile.AccountStatus.ACTIVE,
        )
        self.admin = User.objects.create_superuser("admin@example.com", "hunter222")
        self.staff = User.objects.create_user("staff@example.com", "hunter222", is_staff=True)
        self.member = self._make_user("member@example.com")

    def _make_user(self, email, full_name="", account_status=Profile.AccountStatus.ACTIVE):
        user = User.objects.create_user(email, "hunter222")
        user.profile.full_name = full_name
        user.profile.account_status = account_status
        user.profile.save()
        return user

    def _category(self, name="Electronics"):
        from django.utils.text import slugify

        return Category.objects.create(name=name, slug=slugify(name))

    def _product(self, seller=None, name="Laptop", status=Product.Status.ACTIVE):
        seller = seller or self.seller
        from django.utils.text import slugify

        category = Category.objects.create(name=name, slug=slugify(name))
        return Product.objects.create(
            seller=seller,
            name=name,
            description="A nice thing",
            price=Decimal("1000.00"),
            quantity=5,
            category=category,
            condition="like_new",
            location="Dar es Salaam",
            status=status,
        )

    def _auth(self, user=None):
        self.client.force_authenticate(user=user or self.admin)


class DashboardTests(AdminPanelBase):
    def test_staff_only(self):
        self._auth(self.member)
        resp = self.client.get("/api/admin/dashboard/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn(b"Administrator", resp.content)

    def test_anonymous_denied(self):
        resp = self.client.get("/api/admin/dashboard/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_staff_can_access(self):
        self._auth(self.staff)
        resp = self.client.get("/api/admin/dashboard/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_dashboard_user_and_product_counts(self):
        self._make_user("extra@example.com")
        self._product(name="Laptop A")
        self._product(name="Laptop B", status=Product.Status.INACTIVE)
        self._auth()
        data = self.client.get("/api/admin/dashboard/").data
        self.assertEqual(data["users"]["total"], 5)
        self.assertEqual(data["products"]["total"], 2)
        self.assertEqual(data["products"]["active"], 1)

    def test_recent_activity_entries(self):
        self._product(name="Laptop A")
        self._auth()
        data = self.client.get("/api/admin/dashboard/").data
        self.assertGreaterEqual(len(data["recent_activity"]), 0)
        self.assertTrue(all("type" in e and "message" in e for e in data["recent_activity"]))


class UserManagementTests(AdminPanelBase):
    def test_list(self):
        self._auth()
        resp = self.client.get("/api/admin/users/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        emails = [u["email"] for u in resp.data["results"]]
        self.assertIn("seller@example.com", emails)
        self.assertIn("member@example.com", emails)

    def test_search(self):
        self._auth()
        resp = self.client.get("/api/admin/users/", {"search": "seller"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        emails = [u["email"] for u in resp.data["results"]]
        self.assertEqual(emails, ["seller@example.com"])

    def test_list_non_staff_forbidden(self):
        self._auth(self.member)
        resp = self.client.get("/api/admin/users/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_detail_with_activity(self):
        self._product()
        self._auth()
        resp = self.client.get(f"/api/admin/users/{self.seller.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["product_count"], 1)
        self.assertEqual(str(resp.data["wallet_balance"]), "0.00")

    def test_suspend_and_login_blocked(self):
        self._auth()
        resp = self.client.post(f"/api/admin/users/{self.member.pk}/suspend/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["suspended"])
        self.member.profile.refresh_from_db()
        self.assertEqual(
            self.member.profile.account_status, Profile.AccountStatus.SUSPENDED
        )
        # Suspended user can no longer log in (Prompt 02 login check).
        login = self.client.post(
            "/api/auth/login/",
            {"email": self.member.email, "password": "hunter222"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_400_BAD_REQUEST)

    def test_activate_restores_login(self):
        self.member.profile.account_status = Profile.AccountStatus.SUSPENDED
        self.member.profile.save()
        self._auth()
        resp = self.client.post(f"/api/admin/users/{self.member.pk}/activate/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.member.profile.refresh_from_db()
        self.assertEqual(self.member.profile.account_status, Profile.AccountStatus.ACTIVE)
        login = self.client.post(
            "/api/auth/login/",
            {"email": self.member.email, "password": "hunter222"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)

    def test_cannot_suspend_admin(self):
        self._auth()
        resp = self.client.post(f"/api/admin/users/{self.admin.pk}/suspend/")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_updates_profile_and_email(self):
        self._auth()
        resp = self.client.patch(
            f"/api/admin/users/{self.member.pk}/",
            {
                "email": "renamed@example.com",
                "full_name": "Renamed Member",
                "phone_number": "255700000000",
                "address": "Dodoma",
                "role": "SELLER",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.member.refresh_from_db()
        self.member.profile.refresh_from_db()
        self.assertEqual(self.member.email, "renamed@example.com")
        self.assertEqual(self.member.username, "renamed@example.com")
        self.assertEqual(self.member.profile.full_name, "Renamed Member")
        self.assertEqual(self.member.profile.phone_number, "255700000000")
        self.assertEqual(self.member.profile.address, "Dodoma")
        self.assertEqual(self.member.profile.role, Profile.Role.SELLER)

    def test_patch_rejects_duplicate_email(self):
        self._auth()
        resp = self.client.patch(
            f"/api/admin/users/{self.member.pk}/",
            {"email": self.seller.email},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_cannot_edit_admin(self):
        self._auth()
        resp = self.client.patch(
            f"/api/admin/users/{self.admin.pk}/",
            {"full_name": "Hacked"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_removes_user(self):
        self._auth()
        resp = self.client.delete(f"/api/admin/users/{self.member.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=self.member.pk).exists())

    def test_delete_cannot_remove_admin(self):
        self._auth()
        resp = self.client.delete(f"/api/admin/users/{self.admin.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())


class ProductModerationTests(AdminPanelBase):
    def test_list_includes_inactive(self):
        self._product(name="Active One")
        self._product(name="Hidden One", status=Product.Status.INACTIVE)
        self._auth()
        resp = self.client.get("/api/admin/products/")
        names = [p["name"] for p in resp.data["results"]]
        self.assertIn("Active One", names)
        self.assertIn("Hidden One", names)

    def test_remove_requires_reason(self):
        product = self._product()
        self._auth()
        resp = self.client.post(f"/api/admin/products/{product.pk}/remove/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_remove_deactivates(self):
        product = self._product()
        self._auth()
        resp = self.client.post(
            f"/api/admin/products/{product.pk}/remove/",
            {"reason": "Scam listing"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.INACTIVE)
        self.assertEqual(resp.data["reason"], "Scam listing")

    def test_moderation_forbidden_for_member(self):
        product = self._product()
        self._auth(self.member)
        resp = self.client.post(
            f"/api/admin/products/{product.pk}/remove/",
            {"reason": "no"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class CategoryManagementTests(AdminPanelBase):
    def test_create(self):
        self._auth()
        resp = self.client.post(
            "/api/admin/categories/", {"name": "Books"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Category.objects.filter(name="Books").exists())

    def test_update_deactivate(self):
        category = self._category("Old Name")
        self._auth()
        resp = self.client.patch(
            f"/api/admin/categories/{category.pk}/", {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        category.refresh_from_db()
        self.assertFalse(category.is_active)
