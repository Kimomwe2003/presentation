"""Review endpoints (Prompt 15).

- ``POST /api/reviews/``                      create a review for a COMPLETED purchase
- ``GET  /api/reviews/product/{id}/``         paginated reviews for a product
- ``GET  /api/reviews/seller/{id}/``          seller public profile + aggregated rating + reviews
"""

from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from catalog.models import Product
from catalog.pagination import CatalogPagination
from catalog.serializers import SellerSummarySerializer

from .models import Review
from .serializers import ReviewCreateSerializer, ReviewSerializer


class ReviewCreateView(generics.CreateAPIView):
    """Create a review (server-side completed-purchase restriction)."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ReviewCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        out = ReviewSerializer(review, context={"request": request}).data
        return Response(out, status=status.HTTP_201_CREATED)


class ProductReviewListView(generics.ListAPIView):
    """GET paginated public reviews for a product."""

    permission_classes = [permissions.AllowAny]
    serializer_class = ReviewSerializer
    pagination_class = CatalogPagination

    def get_queryset(self):
        product = get_object_or_404(Product, pk=self.kwargs["product_id"])
        return (
            Review.objects.filter(product=product)
            .select_related("buyer", "buyer__profile", "product")
        )


class SellerPublicProfileView(APIView):
    """GET a seller's public profile with server-computed rating aggregation.

    Returns the seller summary plus ``average_rating`` / ``rating_count`` and a
    paginated ``reviews`` list of that seller's products.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, user_id):
        seller = get_object_or_404(User, pk=user_id)
        reviews = Review.objects.filter(product__seller=seller).select_related("buyer", "product")
        agg = reviews.aggregate(
            average_rating=Avg("rating"),
            rating_count=Count("id"),
        )

        paginator = CatalogPagination()
        page = paginator.paginate_queryset(reviews.order_by("-created_at", "-id"), request)
        reviews_data = ReviewSerializer(page, many=True, context={"request": request}).data

        return Response(
            {
                "seller": SellerSummarySerializer(seller, context={"request": request}).data,
                "average_rating": _round(agg["average_rating"]),
                "rating_count": agg["rating_count"],
                "reviews": {
                    "count": paginator.page.paginator.count if paginator.page else reviews.count(),
                    "next": paginator.get_next_link() if paginator.page else None,
                    "previous": paginator.get_previous_link() if paginator.page else None,
                    "results": reviews_data,
                },
            }
        )


def _round(value):
    if value is None:
        return None
    return round(float(value), 1)
