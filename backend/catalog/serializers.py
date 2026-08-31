"""Serializers for the catalog API."""

from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import User

from .models import Category, Favorite, Product, ProductImage
from .validators import IMAGE_VALIDATORS


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "parent", "is_active"]
        read_only_fields = ["is_active"]


class SellerSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="profile.full_name", read_only=True)
    profile_picture = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "profile_picture", "average_rating", "rating_count"]

    def get_profile_picture(self, obj):
        picture = obj.profile.profile_picture
        if not picture:
            return None
        request = self.context.get("request")
        url = picture.url
        return request.build_absolute_uri(url) if request else url

    def get_average_rating(self, obj):
        return _seller_rating(obj, "average")

    def get_rating_count(self, obj):
        return _seller_rating(obj, "count")


def _seller_rating(seller, key):
    """Server-computed rating aggregation for a seller (single extra query).

    Computed directly over reviews of the seller's products via the Review
    table, so it works regardless of how the seller was fetched.
    """
    from django.db.models import Avg, Count

    from reviews.models import Review

    qs = Review.objects.filter(product__seller=seller)
    if key == "average":
        value = qs.aggregate(a=Avg("rating"))["a"]
        return round(float(value), 1) if value is not None else None
    return qs.aggregate(c=Count("id"))["c"]


class ProductImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ["id", "image", "is_primary", "order"]

    def get_image(self, obj):
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


def primary_or_first_image(product, request):
    """Absolute URL of the product's primary image (fallback: first)."""
    images = list(product.images.all())
    if not images:
        return None
    chosen = next((img for img in images if img.is_primary), None) or images[0]
    url = chosen.image.url
    return request.build_absolute_uri(url) if request else url


class ProductListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    seller = SellerSummarySerializer(read_only=True)
    primary_image = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    rating_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "price",
            "condition",
            "status",
            "location",
            "category",
            "seller",
            "primary_image",
            "average_rating",
            "rating_count",
            "created_at",
        ]

    def get_primary_image(self, obj):
        return primary_or_first_image(obj, self.context.get("request"))

    def get_average_rating(self, obj):
        value = getattr(obj, "avg_rating", None)
        return round(float(value), 1) if value is not None else None


class ProductDetailSerializer(ProductListSerializer):
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            "description",
            "quantity",
            "images",
            "updated_at",
        ]


class ProductWriteSerializer(serializers.ModelSerializer):
    """Create/update a product.

    ``seller`` is never accepted from the request body — it is always taken
    from the authenticated user.
    """

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "price",
            "condition",
            "quantity",
            "location",
            "category",
            "status",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "price": {"min_value": Decimal("0.01")},
            "quantity": {"min_value": 0},
            "category": {"required": False, "allow_null": True},
            "status": {"required": False},
        }

    def validate_status(self, value):
        # INACTIVE is writable so sellers can deactivate/reactivate listings
        # (the quick action in the seller dashboard). SOLD stays read-only —
        # only the order system marks a product sold.
        if value not in (
            Product.Status.DRAFT,
            Product.Status.ACTIVE,
            Product.Status.INACTIVE,
        ):
            raise serializers.ValidationError(
                "Status can only be set to 'DRAFT', 'ACTIVE' or 'INACTIVE'."
            )
        return value

    def validate(self, attrs):
        if self.instance is None:
            attrs.setdefault("status", Product.Status.DRAFT)
        elif "status" not in attrs:
            attrs["status"] = self.instance.status
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        return Product.objects.create(seller=user, **validated_data)


class ProductImageUploadSerializer(serializers.Serializer):
    """Body for ``POST /api/products/{id}/images/``.

    ``images`` is a list of uploaded files; ``is_primary`` marks the first
    image in the batch as primary.
    """

    images = serializers.ListField(
        child=serializers.FileField(),
        allow_empty=False,
        write_only=True,
    )
    is_primary = serializers.BooleanField(required=False, default=False)

    def validate_images(self, value):
        errors = []
        for file_obj in value:
            for validator in IMAGE_VALIDATORS:
                try:
                    validator(file_obj)
                except DjangoValidationError as exc:
                    errors.append(exc.messages[0])
        if errors:
            raise serializers.ValidationError(errors)
        return value


class FavoriteListSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)

    class Meta:
        model = Favorite
        fields = ["id", "product", "created_at"]
