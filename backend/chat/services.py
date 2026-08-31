"""Chat business logic (Prompt 13).

The core rule is **get-or-create by (participants, product)**: starting a chat
from a product's seller reuses an existing conversation between the same two
users about the same product rather than duplicating it. A conversation is
always created with exactly two participants.
"""

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Conversation, Message

User = get_user_model()


class ChatMissingContextError(Exception):
    """Raised when a conversation cannot be created for lack of a counterpart."""


def get_or_create_conversation(*, user, other_user_id=None, product=None):
    """Return (conversation, created) for a one-to-one thread.

    ``user`` is the caller; ``other_user_id`` OR ``product`` (whose seller is
    the counterpart) must be provided. When a product is given the conversation
    is scoped to (caller, seller, product): an existing thread about the same
    product is reused, otherwise a new one is created for this pair.
    """
    if other_user_id is not None and product is not None:
        raise ChatMissingContextError(
            "Pass either other_user_id or product, not both."
        )
    if other_user_id is not None:
        other = User.objects.filter(pk=other_user_id).first()
        if other is None:
            raise ChatMissingContextError("That user does not exist.")
        counterpart = other
        product_ref = None
    elif product is not None:
        counterpart = product.seller
        product_ref = product
    else:
        raise ChatMissingContextError("Specify a user or a product to chat about.")

    if counterpart is None:
        raise ChatMissingContextError("That listing has no seller to contact.")
    if counterpart.pk == user.pk:
        raise ChatMissingContextError("You cannot start a conversation with yourself.")

    query = Conversation.objects.filter(participants=user).filter(
        participants=counterpart, product=product_ref
    )
    existing = query.first()

    if existing is not None:
        return existing, False

    with transaction.atomic():
        created = Conversation.objects.create(product=product_ref)
        created.participants.add(user, counterpart)
    return created, True


def create_message(*, conversation, sender, body: str) -> Message:
    """Create a message, enforcing a sane non-empty length cap."""
    body = body.strip()
    if not body:
        raise ValueError("Message body cannot be empty.")
    if len(body) > 4000:
        raise ValueError("Message is too long (4000 characters max).")
    message = Message.objects.create(
        conversation=conversation, sender=sender, body=body
    )
    _notify_recipient(message)
    return message


def _notify_recipient(message: Message) -> None:
    """Best-effort in-app notification for the other participant.

    The recipient is notified on every inbound message (the sender never is).
    The "recipient not actively viewing" case is handled by in-chat read
    marking plus the notification list's unread badge, rather than by
    suppressing creation — see docs/ARCHITECTURE.md.
    """
    from notifications.services import NotificationService

    recipient = message.conversation.participants.exclude(pk=message.sender_id).first()
    if recipient is None:
        return
    NotificationService.notify(
        user=recipient,
        type_="new_message",
        title="New message",
        body=(
            f"New message from "
            f"{message.sender.get_full_name() or message.sender.username}: "
            f"{message.body}"
        ),
        related_object=message.conversation,
    )
