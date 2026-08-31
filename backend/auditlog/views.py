"""Audit log API views (Prompt 17).

Admin-only, append-only. Only ``GET`` list/detail are exposed — there is no
create/update/delete route for ``AuditLog`` in the API layer (verified by
tests), even for admins. A superuser may still inspect rows via Django admin /
raw DB, which is standard Django behavior and intentionally untouched.
"""

from django_filters import rest_framework as filters
from rest_framework import generics, permissions

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogFilter(filters.FilterSet):
    """Filter the log by actor, action, target model and date range."""

    actor = filters.NumberFilter(field_name="actor_id")
    action = filters.CharFilter(field_name="action", lookup_expr="exact")
    target_model = filters.CharFilter(field_name="target_model", lookup_expr="exact")
    created_after = filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = AuditLog
        fields = ["actor", "action", "target_model", "created_after", "created_before"]


class AuditLogListView(generics.ListAPIView):
    """GET /api/audit-logs/ — admin-only, filterable, newest first."""

    permission_classes = [permissions.IsAdminUser]
    serializer_class = AuditLogSerializer
    filterset_class = AuditLogFilter
    queryset = AuditLog.objects.select_related("actor").order_by("-created_at")


class AuditLogDetailView(generics.RetrieveAPIView):
    """GET /api/audit-logs/{id}/ — admin-only single entry."""

    permission_classes = [permissions.IsAdminUser]
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.select_related("actor")
