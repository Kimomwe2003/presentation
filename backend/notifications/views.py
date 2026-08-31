"""Notification endpoints (Prompt 14).

- ``GET  /api/notifications/``            the caller's notifications (paginated)
- ``POST /api/notifications/{id}/read/``  mark one as read (own only)
- ``POST /api/notifications/read-all/``   mark all the caller's as read
- ``GET  /api/notifications/unread-count/`` unread count for the badge

Security: every endpoint is scoped to ``request.user``; a user can never see or
mark another user's notification.
"""

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(generics.ListAPIView):
    """GET the caller's notifications, newest first."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class NotificationReadView(APIView):
    """POST mark a single notification as read (own only)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: int):
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)


class NotificationReadAllView(APIView):
    """POST mark every notification of the caller as read."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True)
        return Response({"marked_read": updated})


class NotificationUnreadCountView(APIView):
    """GET the caller's unread notification count (for the badge)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        return Response({"unread_count": count})
