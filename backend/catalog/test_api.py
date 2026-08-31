"""API tests for the catalog (Prompt 04)."""

from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile, User
from catalog.models import Category, Favorite, Product, ProductImage
from catalog.tests import png_bytes

PRODUCTS_URL = "/api/products/"
CATEGORIES_URL = "/api/categories/"
FAVORITES_URL = "/api/favorites/"


def make_user(email="seller@example.com"):
    return User.objects.create_user(email=email, password="StrongPass123!")


def make_category(name="Electronics", slug="electronics"):
    return Category.objects.create(name=name, slug=slug)


def make_product(seller, category=None, **overrides):
    values = {
        "name": "Used laptop",
        "description": "Good condition laptop",
        "price": Decimal("150.00"),
        "condition": Product.Condition.GOOD,
        "quantity": 1,
        "location": "Dar es Salaam",
        "status": Product.Status.ACTIVE,
        "category": category or make_category(),
    }
    values.update(overrides)
    return Product.objects.create(seller=seller, **values)


def auth(client, user):
    from rest_framework_simplejwt.tokens import RefreshToken

    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}"
    )


class ProductListTests(APITestCase):
    def setUp(self):
        self.seller = make_user()
        self.category = make_category()
        self.product = make_product(self.seller, self.category)

    def test_list_is_public_and_paginated(self):
        response = self.client.get(PRODUCTS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)

    def test_draft_not_shown_to_public(self):
        make_product(self.seller, self.category, name="Hidden draft", status=Product.Status.DRAFT)
        response = self.client.get(PRODUCTS_URL)
        self.assertEqual(response.data["count"], 1)
        names = [p["name"] for p in response.data["results"]]
        self.assertNotIn("Hidden draft", names)

    def test_draft_visible_to_owner_only(self):
        draft = make_product(
            self.seller, self.category, name="Hidden draft", status=Product.Status.DRAFT
        )
        response = self.client.get(f"{PRODUCTS_URL}{draft.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        auth(self.client, self.seller)
        response = self.client.get(f"{PRODUCTS_URL}{draft.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_returns_images_and_seller(self):
        product = make_product(self.seller, self.category)
        ProductImage.objects.create(
            product=product,
            image=SimpleUploadedFile("pic.png", png_bytes(), content_type="image/png"),
            is_primary=True,
        )
        response = self.client.get(f"{PRODUCTS_URL}{product.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["images"]), 1)
        self.assertEqual(response.data["seller"]["email"], "seller@example.com")
        self.assertIsNotNone(response.data["primary_image"])

    def test_search_returns_subset(self):
        make_product(
            self.seller, self.category, name="Rusty bicycle", price="40.00",
            description="Old bike for spare parts",
        )
        response = self.client.get(PRODUCTS_URL, {"search": "laptop"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Used laptop")

    def test_filter_by_category_condition_price_range(self):
        other_cat = make_category("Furniture", "furniture")
        make_product(
            self.seller,
            self.category,
            name="Cheap phone",
            price="80.00",
            condition=Product.Condition.USED,
        )
        make_product(
            self.seller, other_cat, name="Chair", price="200.00"
        )

        response = self.client.get(
            PRODUCTS_URL,
            {
                "category": self.category.pk,
                "condition": "USED",
                "min_price": "50",
                "max_price": "100",
            },
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Cheap phone")

    def test_pagination_metadata_and_pages(self):
        for i in range(25):
            make_product(
                self.seller, self.category, name=f"Bulk item {i}", price=f"{i + 1}.00"
            )
        response = self.client.get(PRODUCTS_URL)
        self.assertEqual(response.data["count"], 26)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])

        page2 = self.client.get(PRODUCTS_URL, {"page": 2})
        self.assertEqual(len(page2.data["results"]), 6)
        self.assertIsNone(page2.data["next"])
        self.assertIsNotNone(page2.data["previous"])

    def test_categories_list_is_public(self):
        response = self.client.get(CATEGORIES_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class ProductWriteTests(APITestCase):
    def setUp(self):
        self.seller = make_user()
        self.category = make_category()
        self.product = make_product(self.seller, self.category)

    def test_create_requires_auth(self):
        response = self.client.post(
            PRODUCTS_URL,
            {
                "name": "New item",
                "price": "10.00",
                "condition": "NEW",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_sets_seller_from_user_ignoring_body(self):
        buyer = make_user("buyer@example.com")
        auth(self.client, buyer)
        response = self.client.post(
            PRODUCTS_URL,
            {
                "name": "New item",
                "price": "10.00",
                "condition": "NEW",
                "quantity": 1,
                "seller": self.seller.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Product.objects.get(pk=response.data["id"])
        self.assertEqual(created.seller, buyer)
        self.assertEqual(created.status, Product.Status.DRAFT)

    def test_create_sets_status_active_when_provided(self):
        auth(self.client, self.seller)
        response = self.client.post(
            PRODUCTS_URL,
            {
                "name": "Published",
                "price": "10.00",
                "condition": "NEW",
                "status": "ACTIVE",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Product.objects.get(pk=response.data["id"])
        self.assertEqual(created.status, Product.Status.ACTIVE)

    def test_suspended_user_cannot_create(self):
        buyer = make_user("buyer@example.com")
        buyer.profile.account_status = Profile.AccountStatus.SUSPENDED
        buyer.profile.save()
        auth(self.client, buyer)
        response = self.client.post(
            PRODUCTS_URL,
            {"name": "New item", "price": "10.00", "condition": "NEW"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_update(self):
        auth(self.client, self.seller)
        response = self.client.patch(
            f"{PRODUCTS_URL}{self.product.pk}/",
            {"price": "199.99", "status": "ACTIVE"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("199.99"))

    def test_non_owner_cannot_update(self):
        attacker = make_user("attacker@example.com")
        auth(self.client, attacker)
        response = self.client.patch(
            f"{PRODUCTS_URL}{self.product.pk}/",
            {"price": "0.01"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("150.00"))

    def test_non_owner_cannot_delete(self):
        attacker = make_user("attacker@example.com")
        auth(self.client, attacker)
        response = self.client.delete(f"{PRODUCTS_URL}{self.product.pk}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.ACTIVE)

    def test_owner_delete_is_soft(self):
        auth(self.client, self.seller)
        response = self.client.delete(f"{PRODUCTS_URL}{self.product.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.INACTIVE)

        # Hidden from public listing (anonymous client), still visible to owner.
        self.client.credentials()
        public = self.client.get(PRODUCTS_URL)
        self.assertEqual(public.data["count"], 0)
        auth(self.client, self.seller)
        response = self.client.get(f"{PRODUCTS_URL}{self.product.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_owner_can_deactivate_and_reactivate(self):
        auth(self.client, self.seller)
        self.product.status = Product.Status.INACTIVE
        self.product.save(update_fields=["status"])

        # Deactivate is already done; reactivating via PATCH restores it publicly.
        response = self.client.patch(
            f"{PRODUCTS_URL}{self.product.pk}/",
            {"status": "ACTIVE"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.ACTIVE)

        # And a live listing can be paused (deactivated) the same way.
        response = self.client.patch(
            f"{PRODUCTS_URL}{self.product.pk}/",
            {"status": "INACTIVE"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.INACTIVE)

        # SOLD is never settable by the seller directly.
        response = self.client.patch(
            f"{PRODUCTS_URL}{self.product.pk}/",
            {"status": "SOLD"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ProductImageTests(APITestCase):
    def setUp(self):
        self.seller = make_user()
        self.category = make_category()
        self.product = make_product(self.seller, self.category)
        auth(self.client, self.seller)

    def url(self):
        return f"{PRODUCTS_URL}{self.product.pk}/images/"

    def test_owner_uploads_multiple_images_with_primary(self):
        uploads = [
            SimpleUploadedFile("a.png", png_bytes("red"), content_type="image/png"),
            SimpleUploadedFile("b.png", png_bytes("blue"), content_type="image/png"),
        ]
        response = self.client.post(
            self.url(), {"images": uploads, "is_primary": "true"}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 2)
        primaries = self.product.images.filter(is_primary=True)
        self.assertEqual(primaries.count(), 1)
        self.assertEqual(primaries.first().id, response.data[0]["id"])

    def test_first_image_becomes_primary_when_none_exist(self):
        uploads = [
            SimpleUploadedFile("a.png", png_bytes(), content_type="image/png"),
        ]
        response = self.client.post(self.url(), {"images": uploads}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(self.product.images.get(pk=response.data[0]["id"]).is_primary)

    def test_upload_rejects_disallowed_file_type(self):
        uploads = [SimpleUploadedFile("evil.txt", b"nope", content_type="text/plain")]
        response = self.client.post(self.url(), {"images": uploads}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.product.images.count(), 0)

    def test_upload_rejects_non_image_content(self):
        uploads = [
            SimpleUploadedFile("fake.png", b"not an image", content_type="image/png")
        ]
        response = self.client.post(self.url(), {"images": uploads}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_requires_owner(self):
        attacker = make_user("attacker@example.com")
        auth(self.client, attacker)
        uploads = [SimpleUploadedFile("a.png", png_bytes(), content_type="image/png")]
        response = self.client.post(self.url(), {"images": uploads}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_deletes_image_and_promotes_next_primary(self):
        first = ProductImage.objects.create(
            product=self.product,
            image=SimpleUploadedFile("a.png", png_bytes(), content_type="image/png"),
            order=1,
            is_primary=True,
        )
        second = ProductImage.objects.create(
            product=self.product,
            image=SimpleUploadedFile("b.png", png_bytes(), content_type="image/png"),
            order=2,
        )
        response = self.client.delete(
            f"{PRODUCTS_URL}{self.product.pk}/images/{first.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        second.refresh_from_db()
        self.assertTrue(second.is_primary)

    def test_delete_image_requires_owner(self):
        image = ProductImage.objects.create(
            product=self.product,
            image=SimpleUploadedFile("a.png", png_bytes(), content_type="image/png"),
        )
        attacker = make_user("attacker@example.com")
        auth(self.client, attacker)
        response = self.client.delete(
            f"{PRODUCTS_URL}{self.product.pk}/images/{image.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(ProductImage.objects.filter(pk=image.pk).exists())


class FavoriteTests(APITestCase):
    def setUp(self):
        self.seller = make_user()
        self.category = make_category()
        self.product = make_product(self.seller, self.category)
        self.buyer = make_user("buyer@example.com")
        auth(self.client, self.buyer)

    def test_add_remove_list_favorite(self):
        add = self.client.post(f"{FAVORITES_URL}{self.product.pk}/")
        self.assertEqual(add.status_code, status.HTTP_201_CREATED)

        listing = self.client.get(FAVORITES_URL)
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listing.data), 1)
        self.assertEqual(listing.data[0]["product"]["id"], self.product.pk)

        remove = self.client.delete(f"{FAVORITES_URL}{self.product.pk}/")
        self.assertEqual(remove.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.client.get(FAVORITES_URL).data, [])

    def test_add_is_idempotent(self):
        self.client.post(f"{FAVORITES_URL}{self.product.pk}/")
        again = self.client.post(f"{FAVORITES_URL}{self.product.pk}/")
        self.assertEqual(again.status_code, status.HTTP_200_OK)
        self.assertEqual(Favorite.objects.filter(user=self.buyer).count(), 1)

    def test_remove_missing_favorite_returns_404(self):
        response = self.client.delete(f"{FAVORITES_URL}{self.product.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_favorite_another_users_draft(self):
        draft = make_product(
            self.seller, self.category, status=Product.Status.DRAFT
        )
        response = self.client.post(f"{FAVORITES_URL}{draft.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_favorites_requires_auth(self):
        self.client.credentials()
        response = self.client.get(FAVORITES_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
