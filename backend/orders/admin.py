from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("created_at", "updated_at")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "buyer",
        "status",
        "payment_method",
        "total",
        "placed_at",
    )
    list_filter = ("status", "payment_method", "placed_at")
    search_fields = ("order_number", "buyer__email", "buyer__username")
    readonly_fields = (
        "order_number",
        "subtotal",
        "shipping_cost",
        "total",
        "created_at",
        "updated_at",
        "placed_at",
    )
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "product_name",
        "seller",
        "quantity",
        "unit_price",
        "item_status",
    )
    list_filter = ("item_status", "created_at")
    search_fields = ("product_name", "product_sku", "order__order_number")
    readonly_fields = ("created_at", "updated_at")
