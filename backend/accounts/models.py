"""Custom user + profile models.

Identifier strategy (documented decision):

- ``email`` is the *primary* login identifier — it is unique and is the
  ``USERNAME_FIELD`` for Django auth/SimpleJWT.
- ``phone_number`` lives on :class:`Profile` — it is optional but, when
  provided, must be unique across users (usable as a secondary identifier
  later).
- ``username`` is retained for Django admin / legacy compatibility only; it is
  not exposed via the API and is auto-derived from the email on creation.

Role model: there is intentionally NO buyer/seller role on the User or
Profile. Every account is created with identical, full buy+sell capability
(Prompt 02 mandate). If a role split is ever needed, it should be modeled
explicitly and added to the profile then — never smuggled in as a free-text
or enum field now.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Manager keyed on email (the ``USERNAME_FIELD``)."""

    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """ReuseHub user, identified by a unique, case-insensitive email."""

    email = models.EmailField(
        "email address",
        unique=True,
        db_index=True,
        error_messages={"unique": "A user with that email already exists."},
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        # ``username`` is kept only for Django admin/legacy compat; derive it
        # from the email so callers never need to provide it.
        if not self.username:
            self.username = self.email[:150]
        super().save(*args, **kwargs)


class Profile(models.Model):
    """Extended profile data for a user.

    ``account_status`` gates authentication: users whose status is not
    ``ACTIVE`` are rejected at login.
    """

    class AccountStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"

    class Role(models.TextChoices):
        BUYER = "BUYER", "Buyer"
        SELLER = "SELLER", "Seller"
        ADMIN = "ADMIN", "Admin"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    full_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.BUYER,
    )
    profile_picture = models.ImageField(
        upload_to="profiles/",
        blank=True,
        null=True,
    )
    address = models.TextField(blank=True)
    account_status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.ACTIVE,
    )
    phone_number = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        error_messages={"unique": "A user with that phone number already exists."},
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "profile"
        verbose_name_plural = "profiles"

    def __str__(self):
        return f"{self.full_name or self.user.email}"


class PasswordResetCode(models.Model):
    """Single-use, short-lived password-reset code for one user.

    The plain code is never stored — only its SHA-256 hash — so a database
    leak cannot be replayed against the reset endpoint. Codes expire after
    ``CODE_TTL_MINUTES`` and each user only ever has one live code: issuing a
    new one invalidates all previous rows.
    """

    CODE_TTL_MINUTES = 15
    MAX_VERIFY_ATTEMPTS = 5

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_codes",
    )
    code_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "password reset code"
        verbose_name_plural = "password reset codes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"reset code for {self.user.email}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None

    @property
    def is_exhausted(self):
        return self.attempts >= self.MAX_VERIFY_ATTEMPTS

    @classmethod
    def hash_code(cls, code):
        import hashlib

        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    @classmethod
    def issue(cls, user):
        """Generate and store a fresh code for ``user``, invalidating old ones."""
        import secrets

        cls.objects.filter(user=user, used_at__isnull=True).update(
            expires_at=timezone.now()
        )
        code = f"{secrets.randbelow(1000000):06d}"
        return cls.objects.create(
            user=user,
            code_hash=cls.hash_code(code),
            expires_at=timezone.now() + timedelta(minutes=cls.CODE_TTL_MINUTES),
        ), code
