"""Chat models (Prompt 13).

A :class:`Conversation` threads messages between exactly two participants
about (optionally) one product so context survives from listing to discussion.
A :class:`Message` is one participant's turn in a conversation.

Delivery is by client polling: the backend stores the ordering information
``conversation`` + ``created_at`` + ``id`` that the app needs to load pages of
history (newest-first, load-more on scroll) and to poll for new messages. No
WebSocket/Channels dependency is introduced (documented in docs/ARCHITECTURE.md).
"""

from django.conf import settings
from django.db import models


class Conversation(models.Model):
    """A private two-party thread between exactly two users.

    ``product`` is nullable: a conversation may be started from a product's
    "Chat with Seller" button (linking the listing for context) or directly
    with another user without a product reference.
    """

    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="conversations",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self) -> str:
        return f"Conversation({self.id} product={self.product_id})"


class Message(models.Model):
    """One message in a conversation.

    ``is_read`` tracks whether the recipient has opened the thread; the sender's
    own messages are treated as read by definition. Ordering uses
    ``created_at`` with ``id`` as a deterministic tiebreaker, and the
    ``(conversation, created_at, id)`` index drives pagination.
    """

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        db_index=True,
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["conversation", "-created_at", "-id"],
                name="chat_msg_conv_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Message({self.sender_id} -> conv {self.conversation_id})"
