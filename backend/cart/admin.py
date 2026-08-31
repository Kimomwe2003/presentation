from django.contrib import admin

from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "item_count", "is_active", "created_at", "expires_at")
    list_filter = ("is_active", "created_at", "expires_at")
    search_fields = ("owner__email", "owner__username")
    readonly_fields = ("created_at", "updated_at", "expires_at")
    inlines = [CartItemInline]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "product", "quantity", "created_at")
    list_filter = ("created_at",)
    search_fields = ("cart__owner__email", "product__name")
    readonly_fields = ("created_at", "updated_at")
