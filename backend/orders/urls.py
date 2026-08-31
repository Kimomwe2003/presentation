from django.urls import path

from .views import (
    ItemCompleteView,
    ItemConfirmView,
    ItemDeliverView,
    ItemShipView,
    OrderCancelView,
    OrderDetailView,
    OrderListCreateView,
    OrderMarkPaidView,
    OrderRefundView,
    SellerOrderDetailView,
    SellerOrderListView,
)

urlpatterns = [
    path("", OrderListCreateView.as_view(), name="order-list"),
    # Seller-facing routes must precede the buyer <int:pk> route.
    path("selling/", SellerOrderListView.as_view(), name="order-selling-list"),
    path("selling/<int:pk>/", SellerOrderDetailView.as_view(), name="order-selling-detail"),
    path("<int:pk>/", OrderDetailView.as_view(), name="order-detail"),
    path("<int:pk>/cancel/", OrderCancelView.as_view(), name="order-cancel"),
    path("<int:pk>/mark-paid/", OrderMarkPaidView.as_view(), name="order-mark-paid"),
    path("<int:pk>/refund/", OrderRefundView.as_view(), name="order-refund"),
    path("items/<int:item_id>/confirm/", ItemConfirmView.as_view(), name="order-item-confirm"),
    path("items/<int:item_id>/ship/", ItemShipView.as_view(), name="order-item-ship"),
    path("items/<int:item_id>/deliver/", ItemDeliverView.as_view(), name="order-item-deliver"),
    path("items/<int:item_id>/complete/", ItemCompleteView.as_view(), name="order-item-complete"),
]
