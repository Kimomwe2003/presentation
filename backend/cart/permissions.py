from rest_framework import permissions


class IsCartOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_authenticated:
            return obj.cart.owner_id == request.user.pk
        return obj.cart.session_key == request.session.session_key
