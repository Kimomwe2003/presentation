"""Order services: creation and the single transition service (Prompt 08).

All status changes happen here (or in ``state_machine``), never in views.
"""

from django.db import transaction

from .models import Order, OrderItem
from .state_machine import (
    ACTION_CANCEL,
    ACTION_COMPLETE,
    ACTION_CONFIRM,
    ACTION_DELIVER,
    ACTION_FAIL_PAYMENT,
    ACTION_FORCE_CANCEL,
    ACTION_MARK_PAID,
    ACTION_REFUND,
    ACTION_SHIP,
    TransitionDenied,
    apply_transition,
)


def create_order_from_cart(
    *, user, cart, payment_method, shipping_address, shipping_cost=0, request=None
):
    """Create an order + order items from a cart, snapshotting seller/prices."""
    items = list(cart.items.select_related("product", "product__seller"))
    if not items:
        from rest_framework.exceptions import ValidationError

        raise ValidationError({"detail": "Cannot create an order from an empty cart."})
    subtotal = sum(item.line_total for item in items)

    with transaction.atomic():
        order = Order.objects.create(
            buyer=user,
            payment_method=payment_method,
            shipping_address=shipping_address,
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            total=subtotal + shipping_cost,
        )
        for item in items:
            OrderItem.objects.create(
                order=order,
                seller=item.product.seller,
                product=item.product,
                product_name=item.product.name,
                product_sku=getattr(item.product, "sku", ""),
                quantity=item.quantity,
                unit_price=item.product.effective_price(),
                attributes=item.attributes,
            )
        cart.flush()
    from auditlog.services import AuditLogService

    AuditLogService.log(
        actor=user,
        action=AuditLogService.Action.ORDER_CREATE,
        target=order,
        description=f"Order {order.order_number} created ({order.total})",
        request=request,
        after={
            "order_number": order.order_number,
            "status": order.status,
            "total": str(order.total),
        },
    )
    return order


def transition_order(order: Order, action: str, user=None, *, actor=None, request=None) -> Order:
    """Apply an order-level transition and cascade item effects."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        try:
            apply_transition(order, action, user, actor=actor)
        except TransitionDenied:
            raise
        if action in (ACTION_CANCEL, ACTION_FORCE_CANCEL, ACTION_REFUND):
            order.items.update(item_status=OrderItem.Status.CANCELLED)
        elif action == ACTION_MARK_PAID:
            from cart.models import CartItem
            from catalog.models import Product
            from wallet.services import WalletService

            for item in order.items.select_related("product"):
                # Take the product out of every browseable listing the moment
                # it is paid for (sold), and drop it from any carts.
                if item.product:
                    item.product.status = Product.Status.SOLD
                    item.product.save(update_fields=["status", "updated_at"])
                    CartItem.objects.filter(product=item.product).delete()
                # Credit the seller's wallet net of the platform fee as soon as
                # the sale is confirmed by payment. Idempotent (the
                # (order_item, type) ledger constraint) so re-processing is a
                # no-op and the later COMPLETED transition safely short-circuits.
                WalletService.process_completed_sale(item)
        order.save(update_fields=["status", "updated_at"])
    from auditlog.services import AuditLogService

    AuditLogService.log(
        actor=user,
        action=AuditLogService.Action.ORDER_TRANSITION,
        target=order,
        description=f"Order {order.order_number}: {action}",
        request=request,
        after={"action": action, "status": order.status},
    )
    _notify_order_change(order, action)
    return order


def transition_item(
    item: OrderItem, action: str, user=None, *, actor=None, request=None
) -> OrderItem:
    """Apply an item-level transition and sync the order envelope.

    When an item reaches COMPLETED the seller's wallet is credited (net of the
    6% platform fee) via ``WalletService.process_completed_sale`` in the same
    transaction — this is the single, idempotent hook that turns a completed
    sale into earnings (Prompt 10).
    """
    with transaction.atomic():
        item = (
            OrderItem.objects.select_for_update()
            .select_related("order")
            .get(pk=item.pk)
        )
        try:
            apply_transition(item, action, user, actor=actor)
        except TransitionDenied:
            raise
        item.save(update_fields=["item_status", "updated_at"])
        if item.item_status == OrderItem.Status.COMPLETED:
            from wallet.services import WalletService

            WalletService.process_completed_sale(item)
        _sync_order_status(item.order)
    from auditlog.services import AuditLogService

    AuditLogService.log(
        actor=user,
        action=AuditLogService.Action.ORDER_TRANSITION,
        target=item.order,
        description=f"Order {item.order.order_number} item {item.product_name}: {action}",
        request=request,
        after={"action": action, "item_status": item.item_status},
    )
    _notify_item_change(item, action)
    return item


def mark_order_paid(order: Order, user=None, *, actor=None) -> Order:
    """Transition the order to PAID.

    Prompt 09 will call this with ``actor="payment"`` after a successful
    payment; until then it is exposed to admins via ``POST .../mark-paid/``.
    """
    return transition_order(order, ACTION_MARK_PAID, user, actor=actor)


def _sync_order_status(order: Order) -> None:
    """Recompute the envelope state after an item transition.

    When every item is COMPLETED and the order was PAID, the whole order is
    COMPLETED. When every item is CANCELLED the order has no fulfillable
    content; leave the envelope to the order-level flow that cancelled them.
    """
    if order.status != Order.Status.PAID:
        return
    statuses = set(order.items.values_list("item_status", flat=True))
    if statuses and statuses == {OrderItem.Status.COMPLETED}:
        order.status = Order.Status.COMPLETED
        order.save(update_fields=["status", "updated_at"])


def _notify_order_change(order: Order, action: str) -> None:
    """Best-effort in-app notification for the buyer on an order-level change.

    Payment-related actions (paid/failed/refund) use type ``payment_result``;
    other order changes use ``order_update``. On a refund the sellers are also
    notified (their items are cancelled).
    """
    from notifications.services import NotificationService

    paid_like = {ACTION_MARK_PAID, ACTION_FAIL_PAYMENT, ACTION_REFUND}
    type_ = "payment_result" if action in paid_like else "order_update"

    NotificationService.notify(
        user=order.buyer,
        type_=type_,
        title=f"Order {order.get_status_display()}",
        body=(
            f"Order {order.order_number} ({order.total}) is now "
            f"{order.get_status_display()}."
        ),
        related_object=order,
    )

    if action == ACTION_REFUND:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        for seller in User.objects.filter(sold_items__order=order).distinct():
            NotificationService.notify(
                user=seller,
                type_="order_update",
                title="Order refunded",
                body=f"Your item in order {order.order_number} was refunded.",
                related_object=order,
            )


def _notify_item_change(item: OrderItem, action: str) -> None:
    """Best-effort in-app notification for the *other* party on an item change.

    Seller-initiated fulfillment (confirm/ship/deliver) notifies the buyer;
    buyer confirmation of receipt notifies the seller.
    """
    from notifications.services import NotificationService

    if action in (ACTION_CONFIRM, ACTION_SHIP, ACTION_DELIVER):
        user = item.order.buyer
        title = f"Item {item.get_item_status_display()}"
        body = f"{item.product_name} is now {item.get_item_status_display()}."
    elif action == ACTION_COMPLETE:
        user = item.seller
        title = "Item delivered"
        body = f"Buyer confirmed receipt of {item.product_name}."
    else:
        return

    NotificationService.notify(
        user=user,
        type_="order_update",
        title=title,
        body=body,
        related_object=item.order,
    )
