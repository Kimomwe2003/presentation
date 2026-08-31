from django.urls import path

from .views import CartDetailView, CartItemDetailView, CartItemListCreateView

urlpatterns = [
    path("", CartDetailView.as_view(), name="cart-detail"),
    path("items/", CartItemListCreateView.as_view(), name="cart-item-list"),
    path("items/<int:pk>/", CartItemDetailView.as_view(), name="cart-item-detail"),
]
