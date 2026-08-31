from rest_framework import permissions

from .state_machine import actor_for_item


class IsOrderBuyerOrSellerOrAdmin(permissions.BasePermission):
    """Object access for order detail: buyer, an item's seller, or an admin."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True
        if obj.buyer_id == request.user.pk:
            return True
        return obj.items.filter(seller=request.user).exists()


class IsItemParty(permissions.BasePermission):
    """Object access for item actions: the item's seller or the order buyer."""

    def has_object_permission(self, request, view, obj):
        return actor_for_item(request.user, obj) is not None
