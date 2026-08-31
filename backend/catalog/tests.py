"""Model-level tests for the catalog app (Prompt 03)."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from PIL import Image

from accounts.models import User
from catalog.models import Category, Favorite, Product, ProductImage


def make_user(email="seller@example.com"):
    return User.objects.create_user(email=email, password="StrongPass123!")


def make_category(name="Electronics"):
    return Category.objects.create(name=name, slug=name.lower())


def make_product(seller=None, **overrides):
    values = {
        "seller": seller or make_user(),
        "category": make_category(),
        "name": "Used laptop",
        "description": "Good condition",
        "price": Decimal("150.00"),
        "condition": Product.Condition.GOOD,
        "quantity": 1,
        "location": "Dar es Salaam",
        "status": Product.Status.ACTIVE,
    }
    values.update(overrides)
    return Product.objects.create(**values)


def png_bytes(color="red", size=(8, 8)):
    img = Image.new("RGB", size, color)
    import io

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


class ProductConstraintTests(TestCase):
    def test_cannot_create_product_with_negative_price(self):
        seller = make_user()
        category = make_category()
        with self.assertRaises(IntegrityError):
            make_product(
                seller=seller,
                category=category,
                price="-5.00",
            )

    def test_cannot_create_product_with_negative_quantity(self):
        with self.assertRaises(IntegrityError):
            make_product(quantity=-1)

    def test_clean_rejects_negative_price_and_quantity(self):
        product = make_product()
        product.price = Decimal("0.00")
        with self.assertRaises(ValidationError):
            product.clean()
        product.price = Decimal("10.00")
        product.quantity = -3
        with self.assertRaises(ValidationError):
            product.clean()

    def test_valid_product_creates_ok(self):
        product = make_product()
        self.assertEqual(product.status, Product.Status.ACTIVE)
        self.assertEqual(product.price, Decimal("150.00"))


class FavoriteTests(TestCase):
    def test_unique_together_prevents_duplicates(self):
        seller = make_user()
        product = make_product(seller=seller)
        buyer = User.objects.create_user(email="buyer@example.com", password="StrongPass123!")

        Favorite.objects.create(user=buyer, product=product)
        with self.assertRaises(IntegrityError):
            Favorite.objects.create(user=buyer, product=product)

    def test_duplicate_via_clean_rejected(self):
        seller = make_user()
        product = make_product(seller=seller)
        buyer = User.objects.create_user(email="buyer@example.com", password="StrongPass123!")
        Favorite.objects.create(user=buyer, product=product)
        favorite = Favorite(user=buyer, product=product)
        with self.assertRaises(ValidationError):
            favorite.full_clean()


class ProductImageTests(TestCase):
    def test_image_cascades_with_product(self):
        product = make_product()
        image = ProductImage.objects.create(
            product=product,
            image=SimpleUploadedFile("pic.png", png_bytes(), content_type="image/png"),
        )
        self.assertEqual(ProductImage.objects.filter(product=product).count(), 1)
        product.delete()
        self.assertFalse(ProductImage.objects.filter(pk=image.pk).exists())

    def test_image_stored_under_products_dir(self):
        product = make_product()
        image = ProductImage.objects.create(
            product=product,
            image=SimpleUploadedFile("pic.png", png_bytes(), content_type="image/png"),
        )
        self.assertTrue(image.image.name.startswith(f"products/{product.pk}/"))
        self.assertTrue(image.image.name.endswith(".png"))

    def test_image_rejects_unsupported_extension(self):
        product = make_product()
        upload = SimpleUploadedFile("pic.txt", png_bytes(), content_type="text/plain")
        with self.assertRaises(ValidationError):
            ProductImage.objects.create(product=product, image=upload)

    def test_image_rejects_unmatching_mime(self):
        product = make_product()
        upload = SimpleUploadedFile("pic.png", png_bytes(), content_type="application/pdf")
        with self.assertRaises(ValidationError):
            ProductImage.objects.create(product=product, image=upload)

    def test_image_rejects_oversized_file(self):
        product = make_product()
        big = png_bytes() * (5 * 1024 * 1024 // 8 + 1)
        upload = SimpleUploadedFile("big.png", big, content_type="image/png")
        with self.assertRaises(ValidationError):
            ProductImage.objects.create(product=product, image=upload)

    def test_image_rejects_non_image_content(self):
        product = make_product()
        upload = SimpleUploadedFile("fake.png", b"not actually an image", content_type="image/png")
        with self.assertRaises(ValidationError):
            ProductImage.objects.create(product=product, image=upload)


class CategoryTests(TestCase):
    def test_slug_unique(self):
        make_category("Electronics")
        with self.assertRaises(IntegrityError):
            Category.objects.create(name="Another", slug="electronics")

    def test_category_can_have_child(self):
        parent = make_category("Electronics")
        child = Category.objects.create(name="Phones", slug="phones", parent=parent)
        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.children.all())
