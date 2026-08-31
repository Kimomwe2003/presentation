"""Notification service (Prompt 14).

The single entry point for creating in-app notifications. Other apps'
lifecycle services call :func:`notify` at the appropriate points rather than
writing ``Notification`` rows directly, keeping the model an implementation
detail and giving a stable seam where push delivery can be added later.

Notifications are best-effort and never raise: a lifecycle transition must not
fail because a notification could not be written.
"""

from .models import Notification


class NotificationService:
    """Factory for in-app notifications."""

    @staticmethod
    def notify(*, user, type_: str, title: str, body: str = "", related_object=None):
        """Create an in-app notification for ``user``.

        ``related_object`` (any model instance or ``None``) is stored via the
        generic relation so the app can deep-link to the source object.
        Returns the created :class:`Notification` (or ``None`` if the target
        user is missing). Never raises.
        """
        if user is None:
            return None
        try:
            return Notification.objects.create(
                user=user,
                type=type_,
                title=title,
                body=body,
                related_object=related_object,
            )
        except Exception:  # pragma: no cover - defensive, notifications must not break flows
            return None
