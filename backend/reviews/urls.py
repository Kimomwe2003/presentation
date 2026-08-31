from django.urls import path

from .views import ProductReviewListView, ReviewCreateView, SellerPublicProfileView

urlpatterns = [
    path("", ReviewCreateView.as_view(), name="review-create"),
    path("product/<int:product_id>/", ProductReviewListView.as_view(), name="review-list-product"),
    path("seller/<int:user_id>/", SellerPublicProfileView.as_view(), name="review-seller-profile"),
]
