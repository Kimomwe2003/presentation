from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "external_reference",
        "order",
        "amount",
        "provider",
        "status",
        "clickpesa_transaction_id",
        "created_at",
    )
    list_filter = ("provider", "status", "created_at")
    search_fields = ("external_reference", "order__order_number", "clickpesa_transaction_id")
    readonly_fields = ("external_reference", "created_at", "updated_at")
