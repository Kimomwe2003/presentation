"""Audit log model (Prompt 17).

An append-only record of sensitive actions across the system. Rows are created
only via :func:`auditlog.services.AuditLogService.log`; no API route exposes
update/delete for this model (see ``auditlog.views``). Django's own admin is
read-only for staff and the raw DB remains inspectable by a superuser.
"""

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """One immutable record of a sensitive action.

    ``actor`` is nullable so that system-driven events (a payment webhook
    marking an order paid) and anonymous failed logins can still be logged.
    ``before_data`` / ``after_data`` store shallow, sensitive-field-stripped
    snapshots of the affected object.
    """

    class Action(models.TextChoices):
        # accounts
        LOGIN = "auth.login", "Login"
        LOGIN_FAILED = "auth.login_failed", "Login failed"
        LOGOUT = "auth.logout", "Logout"
        REGISTER = "auth.register", "Registration"
        PROFILE_UPDATE = "auth.profile_update", "Profile update"
        PASSWORD_RESET_REQUESTED = (
            "auth.password_reset_requested",
            "Password reset requested",
        )
        PASSWORD_RESET_COMPLETED = (
            "auth.password_reset_completed",
            "Password reset completed",
        )
        # catalog
        PRODUCT_CREATE = "product.create", "Product created"
        PRODUCT_UPDATE = "product.update", "Product updated"
        PRODUCT_DELETE = "product.delete", "Product deleted"
        # orders
        ORDER_CREATE = "order.create", "Order created"
        ORDER_TRANSITION = "order.transition", "Order status changed"
        # payments
        PAYMENT_INITIATE = "payment.initiate", "Payment initiated"
        PAYMENT_SUCCESS = "payment.success", "Payment succeeded"
        PAYMENT_FAILURE = "payment.failure", "Payment failed"
        # withdrawals
        WITHDRAWAL_REQUEST = "withdrawal.request", "Withdrawal requested"
        WITHDRAWAL_TRANSITION = "withdrawal.transition", "Withdrawal status changed"
        # admin moderation
        USER_SUSPEND = "admin.user_suspend", "User suspended"
        USER_ACTIVATE = "admin.user_activate", "User activated"
        USER_UPDATE = "admin.user_update", "User updated"
        USER_DELETE = "admin.user_delete", "User deleted"
        PRODUCT_REMOVE = "admin.product_remove", "Product removed"
        CATEGORY_CREATE = "admin.category_create", "Category created"
        CATEGORY_UPDATE = "admin.category_update", "Category updated"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=64, choices=Action.choices)
    target_model = models.CharField(max_length=64, blank=True, db_index=True)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    before_data = models.JSONField(null=True, blank=True)
    after_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["actor", "created_at"]),
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["target_model", "target_id"]),
        ]
        verbose_name_plural = "audit logs"

    def __str__(self):
        who = self.actor.email if self.actor else "system"
        target = f"{self.target_model}:{self.target_id}" if self.target_id else self.target_model
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.action} by {who} ({target})"
