"""Serializers for the audit log viewer (Prompt 17).

Read-only by design — there is no create/update serializer for ``AuditLog``.
"""

from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.SerializerMethodField()
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor_id",
            "actor_email",
            "action",
            "action_label",
            "target_model",
            "target_id",
            "description",
            "ip_address",
            "before_data",
            "after_data",
            "created_at",
        ]
        read_only_fields = fields

    def get_actor_email(self, obj):
        return obj.actor.email if obj.actor else None
