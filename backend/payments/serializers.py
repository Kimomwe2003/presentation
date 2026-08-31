from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    provider_label = serializers.CharField(source="get_provider_display", read_only=True)
    network_channel = serializers.CharField(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "order",
            "amount",
            "provider",
            "provider_label",
            "status",
            "status_label",
            "network_channel",
            "created_at",
            "failure_reason",
        ]
        read_only_fields = fields
