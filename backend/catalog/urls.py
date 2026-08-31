from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, FavoriteView, ProductViewSet

router = DefaultRouter()
router.register("products", ProductViewSet, basename="product")
router.register("categories", CategoryViewSet, basename="category")

urlpatterns = [
    path("favorites/", FavoriteView.as_view(), name="favorite-list"),
    path("favorites/<int:product_id>/", FavoriteView.as_view(), name="favorite-toggle"),
    path("", include(router.urls)),
]
