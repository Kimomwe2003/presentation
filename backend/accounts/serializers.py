"""API serializers for authentication and user profile management."""

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import Profile, User


class RegisterSerializer(serializers.Serializer):
    """Create a new user.

    Deliberately has no ``role`` field: every account is created with full
    buy+sell capability. ``username`` is never accepted from the client.
    """

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirmation = serializers.CharField(write_only=True, trim_whitespace=False)
    full_name = serializers.CharField(max_length=150, trim_whitespace=False)
    role = serializers.CharField(
        required=False,
        default=Profile.Role.BUYER,
    )
    phone_number = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=20,
        trim_whitespace=False,
    )

    def validate_role(self, value):
        if not value:
            return Profile.Role.BUYER
        val_upper = str(value).strip().upper()
        if val_upper in Profile.Role.values:
            return val_upper
        return Profile.Role.BUYER


    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def validate_phone_number(self, value):
        value = value.strip() or None
        if value and Profile.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("A user with that phone number already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirmation"]:
            raise serializers.ValidationError(
                {"password_confirmation": "The two password fields didn't match."}
            )
        attrs.pop("password_confirmation")
        user = User(email=attrs["email"])
        try:
            validate_password(attrs["password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        full_name = validated_data.pop("full_name").strip()
        phone_number = validated_data.pop("phone_number", None)
        role = validated_data.pop("role", Profile.Role.BUYER)
        email = validated_data.pop("email")
        password = validated_data.pop("password")

        user = User.objects.create_user(email=email, password=password)
        profile = user.profile
        profile.full_name = full_name
        profile.role = role
        if phone_number:
            profile.phone_number = phone_number
        profile.save()
        return user


class LoginSerializer(serializers.Serializer):
    """Authenticate an email + password pair and return the user."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        email = attrs.get("email").strip().lower()
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            email=email,
            password=password,
        )
        if user is None:
            raise serializers.ValidationError(
                {"detail": "Unable to log in with provided credentials."}
            )
        if not user.is_active:
            raise serializers.ValidationError({"detail": "This account is inactive."})
        if user.profile.account_status != Profile.AccountStatus.ACTIVE:
            raise serializers.ValidationError({"detail": "This account has been suspended."})

        attrs["user"] = user
        return attrs


class TokenResponseSerializer(serializers.Serializer):
    refresh = serializers.CharField()
    access = serializers.CharField()


class PasswordForgotSerializer(serializers.Serializer):
    """Request a password-reset code for an email address.

    The response is deliberately identical whether or not the account exists
    so the endpoint cannot be used to enumerate registered emails.
    """

    email = serializers.EmailField(max_length=254)

    def validate_email(self, value):
        return value.strip().lower()


class PasswordResetSerializer(serializers.Serializer):
    """Consume a reset code and set a new password."""

    email = serializers.EmailField(max_length=254)
    code = serializers.RegexField(
        regex=r"^\d{6}$",
        error_messages={"invalid": "Enter the 6-digit code."},
    )
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password_confirmation = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirmation"]:
            raise serializers.ValidationError(
                {"new_password_confirmation": "The two password fields didn't match."}
            )
        email = attrs["email"].strip().lower()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"code": "This reset code is invalid or has expired."}
            )

        from .models import PasswordResetCode

        reset_code = (
            PasswordResetCode.objects.filter(user=user, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if (
            reset_code is None
            or reset_code.is_expired
            or reset_code.is_exhausted
            or reset_code.code_hash != PasswordResetCode.hash_code(attrs["code"])
        ):
            if reset_code is not None and not reset_code.is_expired and not reset_code.is_exhausted:
                reset_code.attempts += 1
                reset_code.save(update_fields=["attempts"])
            raise serializers.ValidationError(
                {"code": "This reset code is invalid or has expired."}
            )

        attrs["user"] = user
        attrs["reset_code"] = reset_code
        return attrs

    def save(self):
        user = self.validated_data["user"]
        reset_code = self.validated_data["reset_code"]
        from django.utils import timezone

        from .models import PasswordResetCode

        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        reset_code.used_at = timezone.now()
        reset_code.save(update_fields=["used_at"])
        # Any other outstanding codes are now stale.
        PasswordResetCode.objects.filter(user=user, used_at__isnull=True).update(
            expires_at=timezone.now()
        )
        return user


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            "full_name",
            "profile_picture",
            "address",
            "phone_number",
            "role",
            "account_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["account_status", "created_at", "updated_at"]


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "date_joined", "is_staff", "profile"]


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["full_name", "profile_picture", "address", "phone_number", "role"]
        extra_kwargs = {
            "full_name": {"required": False},
            "address": {"required": False},
            "phone_number": {"required": False},
            "profile_picture": {"required": False, "allow_null": True},
            "role": {"required": False},
        }

    def validate_phone_number(self, value):
        return value.strip() or None
