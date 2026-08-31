from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ["sender", "body", "is_read", "created_at"]
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "product", "created_at", "updated_at"]
    list_filter = ["created_at"]
    inlines = [MessageInline]
    filter_horizontal = ["participants"]

    def has_add_permission(self, request):
        return False


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "conversation", "sender", "is_read", "created_at"]
    list_filter = ["is_read", "created_at"]
    search_fields = ["body"]
