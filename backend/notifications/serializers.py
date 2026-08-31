"""Serializers for notifications (Prompt 14)."""

from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Read-only notification. ``related`` exposes deep-link info."""

    type_label = serializers.CharField(source="get_type_display", read_only=True)
    related_type = serializers.SerializerMethodField()
    related_id = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "type_label",
            "title",
            "body",
            "is_read",
            "related_type",
            "related_id",
            "created_at",
        ]
        read_only_fields = fields

    def get_related_type(self, obj):
        if obj.content_type is None:
            return None
        return obj.content_type.model

    def get_related_id(self, obj):
        return obj.object_id
