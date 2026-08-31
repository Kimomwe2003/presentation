from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["product", "buyer", "rating", "created_at"]
    list_filter = ["rating", "created_at"]
    search_fields = ["comment", "buyer__email", "product__name"]
