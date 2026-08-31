"""Catalog API views: products, categories, favorites."""

from django.db.models import Avg, Count, Max, Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import ProductFilter
from .models import Category, Favorite, Product, ProductImage
from .pagination import CatalogPagination
from .permissions import IsActiveUser, IsOwnerOrReadOnly
from .serializers import (
    CategorySerializer,
    FavoriteListSerializer,
    ProductDetailSerializer,
    ProductImageSerializer,
    ProductImageUploadSerializer,
    ProductListSerializer,
    ProductWriteSerializer,
)


class ProductViewSet(viewsets.ModelViewSet):
    """CRUD for products.

    - list/retrieve: public (only ACTIVE products; owners see their own drafts)
    - create: authenticated, non-suspended users; ``seller`` = request.user
    - update/delete: owner only; delete is a soft delete (status -> INACTIVE)
    """

    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsActiveUser, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "price", "name"]
    pagination_class = CatalogPagination

    def get_queryset(self):
        queryset = (
            Product.objects.select_related("seller", "category", "seller__profile")
            .prefetch_related("images")
            .annotate(
                # Server-computed product rating aggregation (Prompt 15).
                avg_rating=Avg("reviews__rating"),
                rating_count=Count("reviews"),
            )
        )
        user = self.request.user

        # Detail routes (view/edit/toggle-status/delete one product): the owner
        # must always reach their own listing REGARDLESS of status — otherwise
        # an INACTIVE item could never be re-activated ("No Product matches the
        # given query"). Anonymous visitors still only ever see ACTIVE items,
        # and IsOwnerOrReadOnly blocks strangers from writing.
        if self.action != "list":
            if not user.is_authenticated:
                queryset = queryset.filter(
                    Q(status=Product.Status.ACTIVE) | Q(status=Product.Status.SOLD)
                )
            elif not (user.is_staff or user.is_superuser):
                queryset = queryset.filter(
                    Q(status=Product.Status.ACTIVE)
                    | Q(status=Product.Status.SOLD)
                    | Q(seller=user)
                )
            return queryset.order_by("-created_at", "-id")

        query_params = getattr(self.request, "query_params", self.request.GET)
        seller_param = query_params.get("seller")

        # Seller inbox ("My Listings"): seller sees all their own items regardless of status.
        if seller_param and user.is_authenticated and str(user.id) == str(seller_param):
            queryset = queryset.filter(seller=user)
        # Admin staff view
        elif user.is_authenticated and (user.is_staff or user.is_superuser):
            pass
        else:
            # Public marketplace feed: STRICTLY ACTIVE PRODUCTS ONLY
            queryset = queryset.filter(status=Product.Status.ACTIVE)

        return queryset.order_by("-created_at", "-id")

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        if self.action in ("create", "update", "partial_update"):
            return ProductWriteSerializer
        return ProductDetailSerializer

    def perform_create(self, serializer):
        product = serializer.save()
        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=self.request.user,
            action=AuditLogService.Action.PRODUCT_CREATE,
            target=product,
            description=f"Product created: {product.name}",
            request=self.request,
            after={"name": product.name, "price": str(product.price), "status": product.status},
        )

    def perform_update(self, serializer):
        product = self.get_object()
        before = {
            "name": product.name,
            "price": str(product.price),
            "quantity": product.quantity,
            "status": product.status,
        }
        product = serializer.save()
        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=self.request.user,
            action=AuditLogService.Action.PRODUCT_UPDATE,
            target=product,
            description=f"Product updated: {product.name}",
            request=self.request,
            before=before,
            after={
                "name": product.name,
                "price": str(product.price),
                "quantity": product.quantity,
                "status": product.status,
            },
        )

    def destroy(self, request, *args, **kwargs):
        # Soft delete: keep the record, take it out of the public listing.
        product = self.get_object()
        product.status = Product.Status.INACTIVE
        product.save(update_fields=["status", "updated_at"])
        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=request.user,
            action=AuditLogService.Action.PRODUCT_DELETE,
            target=product,
            description=f"Product deleted: {product.name}",
            request=request,
            after={"status": product.status},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="images")
    def upload_images(self, request, pk=None):
        """Upload one or more images for a product (owner only)."""
        product = self.get_object()
        self.check_object_permissions(request, product)

        serializer = ProductImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        files = serializer.validated_data["images"]
        set_primary = serializer.validated_data.get("is_primary", False)

        has_primary = product.images.filter(is_primary=True).exists()
        next_order = product.images.aggregate(max_order=Max("order"))["max_order"] or 0

        created = []
        for index, file_obj in enumerate(files):
            image = ProductImage.objects.create(
                product=product,
                image=file_obj,
                order=next_order + index + 1,
            )
            if index == 0 and (set_primary or not has_primary):
                image.is_primary = True
                product.images.exclude(pk=image.pk).filter(is_primary=True).update(
                    is_primary=False
                )
                image.save(update_fields=["is_primary"])
                has_primary = True
            created.append(image)

        output = ProductImageSerializer(
            created, many=True, context={"request": request}
        ).data
        return Response(output, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"images/(?P<image_id>[^/.]+)",
    )
    def delete_image(self, request, pk=None, image_id=None):
        """Delete a single image of a product (owner only)."""
        product = self.get_object()
        self.check_object_permissions(request, product)
        image = get_object_or_404(ProductImage, pk=image_id, product=product)

        was_primary = image.is_primary
        image.delete()
        if was_primary:
            next_image = product.images.order_by("order", "id").first()
            if next_image:
                next_image.is_primary = True
                next_image.save(update_fields=["is_primary"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only public categories. Writes arrive with the admin scope (Prompt 16)."""

    permission_classes = [permissions.AllowAny]
    queryset = Category.objects.filter(is_active=True).order_by("name")
    serializer_class = CategorySerializer
    pagination_class = None


class FavoriteView(APIView):
    """Manage the authenticated user's favorites.

    - GET    /api/favorites/                 -> list own favorites
    - POST   /api/favorites/<product_id>/    -> add (idempotent)
    - DELETE /api/favorites/<product_id>/    -> remove
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        favorites = Favorite.objects.filter(user=request.user).select_related(
            "product",
            "product__category",
            "product__seller__profile",
        )
        data = FavoriteListSerializer(
            favorites, many=True, context={"request": request}
        ).data
        return Response(data)

    def post(self, request, product_id=None):
        if product_id is None:
            return Response(
                {"detail": "Product id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        product = get_object_or_404(
            Product, pk=product_id, status=Product.Status.ACTIVE
        )
        _, created = Favorite.objects.get_or_create(user=request.user, product=product)
        payload = {"detail": "Product added to favorites."}
        return Response(
            payload, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    def delete(self, request, product_id=None):
        if product_id is None:
            return Response(
                {"detail": "Product id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        product = get_object_or_404(
            Product, pk=product_id, status=Product.Status.ACTIVE
        )
        deleted, _ = Favorite.objects.filter(user=request.user, product=product).delete()
        if not deleted:
            return Response(
                {"detail": "Favorite not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
