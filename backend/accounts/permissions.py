"""Reusable permissions.

:class:`IsOwner` is the base permission for object ownership checks and will be
reused by business apps (products, orders, chat, ...) in later prompts.
"""

from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """Grant access only when the requester owns the object.

    Resolves the owner from the object's ``user``, ``owner``, or ``created_by``
    attribute (whichever is present), so it works for most models out of the box.
    """

    message = "You do not have permission to perform this action."

    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False
        for attr in ("user", "owner", "created_by"):
            candidate = getattr(obj, attr, None)
            if candidate is not None:
                return candidate == request.user
        return False
