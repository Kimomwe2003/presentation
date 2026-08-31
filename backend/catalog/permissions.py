"""Object-level and active-user permissions for the catalog API."""

from rest_framework import permissions

from accounts.models import Profile


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Allow read-only access to anyone; writes only for the object's owner.

    Works with any model exposing a ``seller``, ``user``, ``owner``, or
    ``created_by`` foreign key to the authenticated user.
    """

    message = "You do not have permission to modify this object."

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not (request.user and request.user.is_authenticated):
            return False
        for attr in ("seller", "user", "owner", "created_by"):
            candidate = getattr(obj, attr, None)
            if candidate is not None:
                return candidate == request.user
        return False


class IsActiveUser(permissions.BasePermission):
    """Require an authenticated, non-suspended user for write operations.

    Reads (GET/HEAD/OPTIONS) are always allowed so browsing stays open.
    """

    message = "Your account is suspended and cannot perform this action."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.profile.account_status == Profile.AccountStatus.ACTIVE
