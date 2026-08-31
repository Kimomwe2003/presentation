"""AuditLogService — the single call point for writing audit entries (Prompt 17).

Every sensitive action in the system logs through :meth:`AuditLogService.log`,
never by constructing :class:`auditlog.models.AuditLog` directly. The service:

- resolves the actor (``None`` → system / anonymous failed login)
- extracts the client IP from ``request`` when available
- stores ``target``'s model name + pk
- strips sensitive fields (passwords, tokens, provider payloads) from snapshots

Design notes
------------
- **Append-only by construction**: there is no update/delete path here or in the
  REST layer; the only sanctioned insert is ``.log()``.
- **No cross-app import cycle**: the service imports the model lazily where a
  plain top-level import is safe; helpers take already-resolved objects.
- **Never raises**: logging must never break the business action it records, so
  a failure to write a row is swallowed (matching the notification pattern).
"""

import logging

from .models import AuditLog

logger = logging.getLogger(__name__)

#: Keys that must never appear in ``before_data`` / ``after_data``.
_SENSITIVE_KEYS = {
    "password",
    "password_confirmation",
    "old_password",
    "new_password",
    "refresh",
    "access",
    "token",
    "raw_provider_response",
    "mobile_money_number",
}


def _client_ip(request):
    """Best-effort client IP from a DRF request (honouring X-Forwarded-For)."""
    if request is None:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _strip_sensitive(data):
    """Recursively drop sensitive keys from a snapshot dict."""
    if not isinstance(data, dict):
        return data
    return {
        key: (_strip_sensitive(value) if isinstance(value, dict) else value)
        for key, value in data.items()
        if key not in _SENSITIVE_KEYS
    }


def _target_ref(target):
    """Return ``(model_name, target_id)`` for an instance or None."""
    if target is None:
        return "", None
    model_name = target._meta.label_lower
    return model_name, target.pk


class AuditLogService:
    """Factory for append-only audit rows."""

    #: Controlled action vocabulary (mirrors ``AuditLog.Action``) so callers can
    #: reference ``AuditLogService.Action.LOGIN`` without importing the model.
    Action = AuditLog.Action

    @staticmethod
    def log(
        *,
        actor,
        action,
        target=None,
        description="",
        request=None,
        before=None,
        after=None,
    ):
        """Persist a single audit row (best-effort, never raises).

        ``actor`` may be a ``User`` instance or ``None`` (system / anonymous).
        ``action`` is one of ``AuditLog.Action`` values (controlled vocabulary).
        ``target`` is any model instance; ``request`` supplies the IP.
        """
        model_name, target_id = _target_ref(target)
        try:
            AuditLog.objects.create(
                actor=actor,
                action=action,
                target_model=model_name,
                target_id=target_id,
                description=description,
                ip_address=_client_ip(request),
                before_data=_strip_sensitive(before),
                after_data=_strip_sensitive(after),
            )
        except Exception:  # noqa: BLE001 — audit writes must never break the action
            logger.exception("Failed to write audit log for %s", action)
