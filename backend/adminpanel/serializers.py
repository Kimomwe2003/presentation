"""Serializers for the adminpanel API (Prompt 16).

The admin surface is API-driven for the mobile admin experience. Serializers
here shape the dashboard aggregation output and moderation views without
creating any new core models.
"""

from rest_framework import serializers

from accounts.models import Profile, User
from catalog.models import Category, Product


class ProfileAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            "full_name",
            "profile_picture",
            "phone_number",
            "address",
            "account_status",
            "created_at",
        ]
        read_only_fields = fields


class UserAdminSerializer(serializers.ModelSerializer):
    profile = ProfileAdminSerializer(read_only=True)
    is_suspended = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "is_staff",
            "is_superuser",
            "is_active",
            "date_joined",
            "is_suspended",
            "profile",
        ]
        read_only_fields = fields

    def get_is_suspended(self, obj) -> bool:
        return obj.profile.account_status == Profile.AccountStatus.SUSPENDED


class UserAdminUpdateSerializer(serializers.ModelSerializer):
    """PATCH body for admin editing of a member account.

    ``email`` lives on ``User``; the profile fields (``full_name``,
    ``phone_number``, ``address``) live on ``Profile``. ``role`` is a profile
    field but is editable here for admin management (see ``accounts.models``
    for the documented role model). Admin accounts are protected at the view
    layer.
    """

    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone_number = serializers.CharField(
        max_length=20, required=False, allow_blank=True, allow_null=True
    )
    address = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(
        choices=Profile.Role.choices, required=False
    )

    class Meta:
        model = User
        fields = [
            "email",
            "full_name",
            "phone_number",
            "address",
            "role",
        ]

    def validate_email(self, value):
        value = value.strip().lower()
        qs = User.objects.filter(email__iexact=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def validate_phone_number(self, value):
        if value in ("", None):
            return None
        qs = Profile.objects.filter(phone_number=value)
        profile = getattr(self.instance, "profile", None) if self.instance else None
        if profile is not None:
            qs = qs.exclude(pk=profile.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A user with that phone number already exists."
            )
        return value

    def update(self, instance, validated_data):
        email = validated_data.pop("email", None)
        if email:
            instance.email = email
            instance.username = email[:150]
        role = validated_data.pop("role", None)
        profile_fields = {}
        for field in ("full_name", "phone_number", "address"):
            if field in validated_data:
                profile_fields[field] = validated_data[field]
        if role is not None:
            profile_fields["role"] = role
        instance.save()
        if profile_fields:
            profile = getattr(instance, "profile", None)
            if profile is not None:
                for k, v in profile_fields.items():
                    setattr(profile, k, v)
                profile.save()
        return instance


class UserAdminDetailSerializer(UserAdminSerializer):
    """User detail: base fields plus aggregated activity summary."""

    product_count = serializers.IntegerField(read_only=True)
    order_count = serializers.IntegerField(read_only=True)
    sold_count = serializers.IntegerField(read_only=True)
    wallet_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta(UserAdminSerializer.Meta):
        fields = UserAdminSerializer.Meta.fields + [
            "product_count",
            "order_count",
            "sold_count",
            "wallet_balance",
        ]


class ProductAdminSerializer(serializers.ModelSerializer):
    seller = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    image_url = serializers.SerializerMethodField()
    review_count = serializers.IntegerField(read_only=True)
    average_rating = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "price",
            "condition",
            "quantity",
            "status",
            "location",
            "seller",
            "category",
            "category_name",
            "image_url",
            "review_count",
            "average_rating",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_seller(self, obj) -> dict:
        seller = obj.seller
        profile = getattr(seller, "profile", None)
        return {
            "id": seller.pk,
            "email": seller.email,
            "full_name": profile.full_name if profile and profile.full_name else seller.email,
        }

    def get_image_url(self, obj):
        request = self.context.get("request")
        images = list(obj.images.all())
        if not images:
            return None
        chosen = next((img for img in images if img.is_primary), None) or images[0]
        url = chosen.image.url
        return request.build_absolute_uri(url) if request else url

    def get_average_rating(self, obj):
        value = getattr(obj, "avg_rating", None)
        return round(float(value), 1) if value is not None else None


class ProductRemoveSerializer(serializers.Serializer):
    """Body for ``POST /api/admin/products/{id}/remove/``.

    ``reason`` is required (fed to the Prompt 17 audit log).
    """

    reason = serializers.CharField(max_length=500)

    def validate_reason(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("A reason is required for removal.")
        return value


class CategoryAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "parent", "is_active"]
        read_only_fields = ["id"]
        extra_kwargs = {"slug": {"required": False}}

    def validate(self, attrs):
        if not attrs.get("slug") and attrs.get("name"):
            from django.utils.text import slugify

            attrs["slug"] = slugify(attrs["name"])
        return attrs
