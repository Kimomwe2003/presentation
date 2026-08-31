from decimal import Decimal

from rest_framework import serializers

from core.utils import int_to_pretty

from .models import Order, OrderItem
from .state_machine import available_actions


class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(read_only=True)
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    seller = serializers.SerializerMethodField()
    item_status_label = serializers.CharField(source="get_item_status_display", read_only=True)
    available_actions = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product_id",
            "product_name",
            "product_sku",
            "quantity",
            "unit_price",
            "attributes",
            "item_status",
            "item_status_label",
            "seller",
            "line_total",
            "available_actions",
        ]
        read_only_fields = fields

    def get_seller(self, obj) -> dict:
        seller = obj.seller
        if seller is None:
            return None
        profile = getattr(seller, "profile", None)
        full_name = profile.full_name if profile else ""
        return {"id": seller.pk, "full_name": full_name or seller.email}

    def get_available_actions(self, obj) -> list[dict]:
        return available_actions(obj, self.context.get("request").user)


class OrderSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    total_pretty = serializers.SerializerMethodField()
    buyer = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "status_label",
            "payment_method",
            "shipping_address",
            "subtotal",
            "shipping_cost",
            "total",
            "total_pretty",
            "placed_at",
            "buyer",
            "items",
            "available_actions",
        ]
        read_only_fields = fields

    def get_total_pretty(self, obj) -> str:
        return int_to_pretty(obj.total)

    def get_buyer(self, obj) -> dict:
        buyer = obj.buyer
        if buyer is None:
            return None
        profile = getattr(buyer, "profile", None)
        return {
            "id": buyer.pk,
            "email": buyer.email,
            "full_name": profile.full_name if profile else "",
            "phone_number": profile.phone_number if profile else None,
        }

    def get_items(self, obj) -> list[dict]:
        request = self.context.get("request")
        user = request.user if request else None
        items = obj.items.all()
        # Sellers see only their own lines (multi-seller order privacy).
        if user is not None and user.is_authenticated:
            is_admin = user.is_staff or user.is_superuser
            if not is_admin and getattr(obj, "buyer_id", None) != user.pk:
                items = items.filter(seller=user)
        return OrderItemSerializer(items, many=True, context=self.context).data

    def get_available_actions(self, obj) -> list[dict]:
        return available_actions(obj, self.context.get("request").user)


class OrderCreateSerializer(serializers.ModelSerializer):
    shipping_address = serializers.JSONField(required=False, default=dict)
    shipping_cost = serializers.DecimalField(
        required=False,
        min_value=Decimal("0.00"),
        default=Decimal("0.00"),
        max_digits=10,
        decimal_places=2,
    )

    class Meta:
        model = Order
        fields = ["payment_method", "shipping_address", "shipping_cost"]
