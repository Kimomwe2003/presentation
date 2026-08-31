from rest_framework import serializers

from .models import LedgerTransaction


class WalletBalanceSerializer(serializers.Serializer):
    """Balance summary. Serialized so Decimals render as API strings."""

    balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_withdrawn = serializers.DecimalField(max_digits=12, decimal_places=2)


class LedgerTransactionSerializer(serializers.ModelSerializer):
    """Read-only ledger row. No write serializer exists — balance is never mutable."""

    type_label = serializers.CharField(source="get_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    order_item_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = LedgerTransaction
        fields = [
            "id",
            "type",
            "type_label",
            "amount",
            "status",
            "status_label",
            "reference",
            "description",
            "order_item_id",
            "created_at",
        ]
        read_only_fields = fields
