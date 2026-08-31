from django.contrib import admin

from .models import WithdrawalRequest


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "user",
        "amount",
        "provider",
        "mobile_money_number",
        "status",
        "created_at",
        "processed_at",
    ]
    list_filter = ["status", "provider"]
    search_fields = ["reference", "mobile_money_number", "user__email"]
    readonly_fields = ["user", "amount", "provider", "mobile_money_number", "reference", "created_at"]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        # Requests are created through the API, never the admin shell.
        return False