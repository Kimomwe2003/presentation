from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from cart.services import get_current_cart, merge_anonymous_cart_to_user

from .models import Order, OrderItem
from .permissions import IsOrderBuyerOrSellerOrAdmin
from .serializers import OrderCreateSerializer, OrderSerializer
from .services import (
    create_order_from_cart,
    transition_item,
    transition_order,
)
from .state_machine import (
    ACTION_CANCEL,
    ACTION_COMPLETE,
    ACTION_CONFIRM,
    ACTION_DELIVER,
    ACTION_MARK_PAID,
    ACTION_REFUND,
    ACTION_SHIP,
    TransitionDenied,
)


def _transition_error_response(exc: TransitionDenied) -> Response:
    code = 403 if exc.code == "permission_denied" else 400
    return Response({"detail": str(exc)}, status=code)


class OrderListCreateView(generics.ListCreateAPIView):
    """Buyer's orders: list + create from the current cart (admins see all orders)."""

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Order.objects.all().select_related("buyer").prefetch_related("items")
        return (
            Order.objects.filter(buyer=user)
            .select_related("buyer")
            .prefetch_related("items")
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return OrderCreateSerializer
        return OrderSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        merge_anonymous_cart_to_user(request)
        cart = get_current_cart(request)
        order = create_order_from_cart(
            user=request.user,
            cart=cart,
            payment_method=serializer.validated_data.get("payment_method", "card"),
            shipping_address=serializer.validated_data.get("shipping_address", {}),
            shipping_cost=serializer.validated_data.get("shipping_cost", 0),
            request=request,
        )
        response_serializer = OrderSerializer(
            order, context={"request": request}
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class OrderDetailView(generics.RetrieveAPIView):
    """Buyer's order detail (admins see all orders)."""

    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Order.objects.all().select_related("buyer").prefetch_related("items")
        return (
            Order.objects.filter(buyer=user)
            .select_related("buyer")
            .prefetch_related("items")
        )


class SellerOrderListView(generics.ListAPIView):
    """Orders containing the current user's items (seller's inbox).

    ``?item_status=`` narrows to orders that contain at least one of the
    user's items in the given fulfillment state (shipped, delivered, ...).
    """

    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        base = Order.objects.filter(items__seller=self.request.user)
        item_status = self.request.query_params.get("item_status")
        if item_status:
            base = base.filter(items__item_status=item_status)
        return (
            base.select_related("buyer")
            .prefetch_related("items")
            .distinct()
        )


class SellerOrderDetailView(generics.RetrieveAPIView):
    """Seller's view of an order (only their items are serialized)."""

    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrderBuyerOrSellerOrAdmin]

    def get_queryset(self):
        return (
            Order.objects.filter(items__seller=self.request.user)
            .select_related("buyer")
            .prefetch_related("items")
            .distinct()
        )


class OrderActionView(APIView):
    """POST /api/orders/{id}/<action>/ — order-level transitions only."""

    permission_classes = [permissions.IsAuthenticated]
    action: str

    def get_order(self, pk: int) -> Order:
        # The state machine enforces the actor role; we still require the user
        # to be a party to (or admin of) the order before acting.
        order = get_object_or_404(
            Order.objects.prefetch_related("items"), pk=pk
        )
        if not (request_user_is_party(self.request.user, order)):
            from rest_framework.exceptions import NotFound

            raise NotFound()
        return order

    def post(self, request, pk: int):
        order = self.get_order(pk)
        try:
            order = transition_order(order, self.action, request.user, request=request)
        except TransitionDenied as exc:
            return _transition_error_response(exc)
        serializer = OrderSerializer(order, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderCancelView(OrderActionView):
    action = ACTION_CANCEL


class OrderMarkPaidView(OrderActionView):
    action = ACTION_MARK_PAID


class OrderRefundView(OrderActionView):
    action = ACTION_REFUND


class ItemActionView(APIView):
    """POST /api/orders/items/{id}/<action>/ — item-level transitions."""

    permission_classes = [permissions.IsAuthenticated]
    action: str

    def get_item(self, item_id: int) -> OrderItem:
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return get_object_or_404(OrderItem, pk=item_id)
        return get_object_or_404(
            OrderItem.objects.filter(
                order__buyer=user
            ) | OrderItem.objects.filter(seller=user),
            pk=item_id,
        )

    def post(self, request, item_id: int):
        item = self.get_item(item_id)
        try:
            item = transition_item(item, self.action, request.user, request=request)
        except TransitionDenied as exc:
            return _transition_error_response(exc)
        order = Order.objects.prefetch_related("items").get(pk=item.order_id)
        serializer = OrderSerializer(order, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ItemConfirmView(ItemActionView):
    action = ACTION_CONFIRM


class ItemShipView(ItemActionView):
    action = ACTION_SHIP


class ItemDeliverView(ItemActionView):
    action = ACTION_DELIVER


class ItemCompleteView(ItemActionView):
    action = ACTION_COMPLETE


def request_user_is_party(user, order: Order) -> bool:
    if user.is_staff or user.is_superuser:
        return True
    if order.buyer_id == user.pk:
        return True
    return order.items.filter(seller=user).exists()
