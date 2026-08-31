from rest_framework import permissions


class IsOrderBuyer(permissions.BasePermission):
    """Object access for payment endpoints: the order's buyer (or an admin)."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True
        return obj.buyer_id == request.user.pk
