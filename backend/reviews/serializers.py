"""Serializers for reviews (Prompt 15)."""

from rest_framework import serializers

from orders.models import OrderItem

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    """Read view of a review, with buyer/product convenience fields."""

    buyer = serializers.SerializerMethodField()
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = Review
        fields = [
            "id",
            "order_item",
            "buyer",
            "product",
            "product_name",
            "rating",
            "comment",
            "created_at",
        ]
        read_only_fields = ["id", "order_item", "buyer", "product", "product_name", "created_at"]

    def get_buyer(self, obj) -> dict:
        profile = getattr(obj.buyer, "profile", None)
        return {
            "id": obj.buyer.pk,
            "full_name": profile.full_name if profile and profile.full_name else obj.buyer.email,
        }


class ReviewCreateSerializer(serializers.ModelSerializer):
    """Write-only creation serializer that enforces the purchase restriction.

    The buyer is always ``request.user`` (never trusted from the body); the
    product is taken from the validated order item. A review is only permitted
    when the requester is the buyer of a COMPLETED order item, and only once
    per order item.
    """

    order_item_id = serializers.PrimaryKeyRelatedField(
        queryset=OrderItem.objects.all(), source="order_item"
    )

    class Meta:
        model = Review
        fields = ["order_item_id", "rating", "comment"]

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def validate(self, attrs):
        order_item = attrs["order_item"]
        user = self.context["request"].user

        if order_item.order.buyer_id != user.pk:
            raise serializers.ValidationError(
                {"order_item": "You can only review an item you purchased."}
            )
        if order_item.item_status != OrderItem.Status.COMPLETED:
            raise serializers.ValidationError(
                {"order_item": "You can only review an item after it has been completed."}
            )
        if Review.objects.filter(order_item=order_item).exists():
            raise serializers.ValidationError(
                {"order_item": "You have already reviewed this order item."}
            )
        return attrs

    def create(self, validated_data):
        order_item = validated_data.pop("order_item")
        user = self.context["request"].user
        return Review.objects.create(
            order_item=order_item,
            buyer=user,
            product=order_item.product,
            **validated_data,
        )
