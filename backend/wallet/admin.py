from django.contrib import admin

from .models import LedgerTransaction, Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "updated_at")
    search_fields = ("user__email",)
    # Balance is never edited by hand — it is reconciled from the ledger by
    # WalletService, so no balance field is exposed for editing here.
    readonly_fields = ("user", "balance", "updated_at")


@admin.register(LedgerTransaction)
class LedgerTransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "amount", "status", "order_item", "created_at")
    list_filter = ("type", "status", "created_at")
    search_fields = ("user__email", "reference", "order_item__product_name")
    readonly_fields = (
        "user",
        "amount",
        "type",
        "status",
        "order_item",
        "reference",
        "description",
        "created_at",
    )
