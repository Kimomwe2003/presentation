"""Notification model (Prompt 14).

In-app notifications are created by :mod:`notifications.services` from the
lifecycle services of other apps (orders, payments, withdrawals, chat). The
model uses a generic relation (``content_type``/``object_id``) so a
notification can point at an order, payment, withdrawal request or chat
conversation, letting the app navigate to the related object when tapped.

Push delivery is intentionally **deferred** (see docs/ARCHITECTURE.md): this
model stores the in-app row only. A future enhancement may add a push-token
model and send via Expo's push API without changing the notify signature.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Notification(models.Model):
    """A single user-facing event, shown in the in-app notification list."""

    class Type(models.TextChoices):
        ORDER_UPDATE = "order_update", "Order update"
        PAYMENT_RESULT = "payment_result", "Payment result"
        NEW_MESSAGE = "new_message", "New message"
        WITHDRAWAL_UPDATE = "withdrawal_update", "Withdrawal update"
        SYSTEM = "system", "System"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_index=True,
    )
    type = models.CharField(max_length=32, choices=Type.choices, db_index=True)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    is_read = models.BooleanField(default=False, db_index=True)

    # Optional pointer to the object the notification is about.
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey("content_type", "object_id")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["user", "is_read", "-created_at"],
                name="notif_user_read_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_type_display()}: {self.title} ({self.user_id})"
