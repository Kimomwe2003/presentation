"""Serializers for withdrawal requests (Prompt 12).

The write serializer only accepts the fields a user provides; the reference,
status and balance movement are produced by :mod:`withdrawals.services`.
"""

from rest_framework import serializers

from .models import MIN_WITHDRAWAL_AMOUNT, WithdrawalRequest
from .services import WithdrawalService


class WithdrawalRequestSerializer(serializers.ModelSerializer):
    """Read model: a user's request with its provider/status labels."""

    provider_label = serializers.CharField(source="get_provider_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = WithdrawalRequest
        fields = [
            "id",
            "amount",
            "provider",
            "provider_label",
            "mobile_money_number",
            "status",
            "status_label",
            "reference",
            "admin_notes",
            "payout_reference",
            "payout_status",
            "payout_message",
            "created_at",
            "processed_at",
        ]
        read_only_fields = [
            "status",
            "status_label",
            "reference",
            "payout_reference",
            "payout_status",
            "payout_message",
            "processed_at",
        ]


class WithdrawalCreateSerializer(serializers.Serializer):
    """User-submitted payout details. No balance writes happen here."""

    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=MIN_WITHDRAWAL_AMOUNT
    )
    provider = serializers.ChoiceField(choices=WithdrawalRequest.Provider.choices)
    mobile_money_number = serializers.CharField(max_length=32)

    def validate_mobile_money_number(self, value: str) -> str:
        digits = value.strip()
        if not digits.isdigit() or len(digits) < 9 or len(digits) > 12:
            raise serializers.ValidationError(
                "Enter a valid mobile money number (9-12 digits)."
            )
        return digits

    def create(self, validated_data):
        return WithdrawalService.request_withdrawal(
            self.context["request"].user,
            amount=validated_data["amount"],
            provider=validated_data["provider"],
            mobile_money_number=validated_data["mobile_money_number"],
        )
