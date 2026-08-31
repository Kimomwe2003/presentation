from rest_framework import serializers

from catalog.models import Product
from catalog.serializers import primary_or_first_image
from core.utils import int_to_pretty

from .models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(min_value=1)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_image = serializers.SerializerMethodField()
    condition = serializers.CharField(source="product.condition", read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product_id",
            "product_name",
            "product_image",
            "condition",
            "quantity",
            "attributes",
            "price",
            "total",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "product_name",
            "product_image",
            "condition",
            "price",
            "total",
            "created_at",
        ]

    def get_product_image(self, obj) -> str | None:
        return primary_or_first_image(obj.product, self.context.get("request"))

    def validate_quantity(self, value: int) -> int:
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        if value > 100:
            raise serializers.ValidationError("Quantity cannot exceed 100.")
        return value

    def validate(self, attrs):
        product_id = attrs.get("product_id")
        if product_id is not None:
            product = Product.objects.filter(pk=product_id).first()
            if product is None or product.status != Product.Status.ACTIVE:
                raise serializers.ValidationError({"product_id": "Product not available."})
        return attrs


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    subtotal_pretty = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "item_count",
            "subtotal",
            "subtotal_pretty",
            "created_at",
        ]

    def get_subtotal_pretty(self, obj) -> str:
        return int_to_pretty(obj.subtotal)
