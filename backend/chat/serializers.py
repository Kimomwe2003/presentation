"""Serializers for chat (Prompt 13).

The conversation serializer exposes the counterpart (the "other" participant
relative to the requesting user) plus the last message preview and unread
count used by the conversation list UI. Message serializers are read/write and
always scoped to a participant (enforced in the views).
"""

from rest_framework import serializers

from catalog.serializers import SellerSummarySerializer as SellerSerializer

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    """A message with sender detail. ``is_read`` is set server-side on read."""

    sender = serializers.PrimaryKeyRelatedField(read_only=True)
    sender_detail = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "sender",
            "sender_detail",
            "body",
            "is_read",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "conversation",
            "sender",
            "sender_detail",
            "is_read",
            "created_at",
        ]

    def get_sender_detail(self, obj):
        return {
            "id": obj.sender_id,
            "email": obj.sender.email,
            "full_name": obj.sender.profile.full_name,
        }


class ConversationSerializer(serializers.ModelSerializer):
    """A conversation for the requesting user, pivoting to the counterpart."""

    counterpart = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    product_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id",
            "counterpart",
            "product_id",
            "last_message",
            "unread_count",
            "created_at",
            "updated_at",
        ]

    def get_counterpart(self, obj):
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            other = obj.participants.exclude(pk=request.user.pk).first()
            if other is not None:
                return SellerSerializer(other).data
        return None

    def get_last_message(self, obj):
        last = obj.messages.order_by("-created_at", "-id").first()
        if last is None:
            return None
        return {
            "id": last.id,
            "sender": last.sender_id,
            "body": last.body,
            "is_read": last.is_read,
            "created_at": last.created_at,
        }

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return 0
        return obj.messages.filter(
            is_read=False
        ).exclude(sender=request.user).count()
