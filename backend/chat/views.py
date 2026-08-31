"""Chat endpoints (Prompt 13).

- ``GET  /api/chats/``                 list the caller's conversations
- ``POST /api/chats/``                 get-or-create a conversation
- ``GET  /api/chats/{id}/messages/``   paginated message history (newest first)
- ``POST /api/chats/{id}/messages/``   send a message
- ``POST /api/chats/{id}/read/``       mark the thread as read

Security: every conversation/message endpoint enforces that the requesting user
is a participant (a non-participant sees 404). Message length is validated by
:func:`chat.services.create_message`.
"""

from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product

from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer
from .services import ChatMissingContextError, create_message, get_or_create_conversation


def _owned(request):
    """Return conversations the requesting user is a participant of."""
    return Conversation.objects.filter(participants=request.user)


class ConversationListCreateView(generics.ListCreateAPIView):
    """GET own conversations (most recently active first) + get-or-create."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return _owned(self.request).prefetch_related("participants", "messages")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def create(self, request, *args, **kwargs):
        product_id = request.data.get("product_id")
        other_user_id = request.data.get("other_user_id")

        product = None
        if product_id is not None:
            product = Product.objects.filter(pk=product_id).first()
            if product is None:
                raise NotFound("That product does not exist.")

        try:
            conversation, _created = get_or_create_conversation(
                user=request.user,
                other_user_id=other_user_id,
                product=product,
            )
        except ChatMissingContextError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        serializer = self.get_serializer(conversation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ConversationParticipantMixin:
    """Object-level security: only participants may access a conversation."""

    def get_conversation(self, pk: int) -> Conversation:
        conversation = (
            _owned(self.request).filter(pk=pk).first()
        )
        if conversation is None:
            raise NotFound("Conversation not found.")
        return conversation


class MessageView(APIView, ConversationParticipantMixin):
    """GET paginated history + POST a new message for a conversation."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk: int):
        conversation = self.get_conversation(pk)
        messages = Message.objects.filter(conversation=conversation).select_related(
            "sender", "sender__profile"
        )
        return self._paginate(request, messages)

    def _paginate(self, request, messages):
        page_size = int(request.query_params.get("page_size", 50))
        page_size = max(1, min(page_size, 100))
        page = int(request.query_params.get("page", 1))
        total = messages.count()
        limit = page * page_size
        items = list(messages[:limit])
        start = max(0, limit - page_size)
        items = items[start:limit]
        has_more = total > limit
        serializer = MessageSerializer(items, many=True, context={"request": request})
        return Response(
            {
                "results": serializer.data,
                "next": f"?page={page + 1}" if has_more else None,
                "count": total,
            }
        )

    def post(self, request, pk: int):
        conversation = self.get_conversation(pk)
        body = request.data.get("body", "")
        if isinstance(body, str):
            body = body[:4000]
        try:
            message = create_message(
                conversation=conversation, sender=request.user, body=body
            )
        except ValueError as exc:
            raise ValidationError({"body": str(exc)}) from exc
        return Response(
            MessageSerializer(message).data, status=status.HTTP_201_CREATED
        )


class MarkThreadReadView(APIView, ConversationParticipantMixin):
    """POST mark all messages from others as read."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk: int):
        conversation = self.get_conversation(pk)
        updated = Message.objects.filter(
            conversation=conversation, is_read=False
        ).exclude(sender=request.user).update(is_read=True)
        return Response({"marked_read": updated})
