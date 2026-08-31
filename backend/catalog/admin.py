from django.contrib import admin

from .models import Category, Favorite, Product, ProductImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "parent", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "seller",
        "category",
        "price",
        "condition",
        "quantity",
        "status",
        "created_at",
    ]
    list_filter = ["status", "condition", "category", "seller"]
    search_fields = ["name", "description", "seller__email", "location"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [ProductImageInline]
    autocomplete_fields = ["seller", "category"]

    @admin.display(boolean=True, description="Active category")
    def is_active_category(self, obj):
        return obj.category.is_active if obj.category else None


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ["id", "product", "is_primary", "order", "created_at"]
    list_filter = ["is_primary"]
    search_fields = ["product__name"]


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ["user", "product", "created_at"]
    search_fields = ["user__email", "product__name"]
