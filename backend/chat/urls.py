from django.urls import path

from .views import (
    ConversationListCreateView,
    MarkThreadReadView,
    MessageView,
)

urlpatterns = [
    path("", ConversationListCreateView.as_view(), name="chat-list-create"),
    path("<int:pk>/messages/", MessageView.as_view(), name="chat-messages"),
    path("<int:pk>/read/", MarkThreadReadView.as_view(), name="chat-read"),
]
