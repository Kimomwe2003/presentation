"""Order/order-item state machine (Prompt 08).

Single source of truth for every status transition. Views and serializers never
write ``status`` / ``item_status`` directly — they call the services module,
which funnels through :func:`apply_transition` here.

Design decisions (documented in docs/ARCHITECTURE.md):

- ``Order.status`` is the payment/envelope state; ``OrderItem.item_status`` is
  the per-seller fulfillment state.
- A transition is allowed only when BOTH the (current_status, action) entry
  exists in the table AND the acting user holds the required role for that
  action (object-level — "is this the buyer / the item's seller / an admin").
- ``actor="payment"`` is reserved for internal payment code (Prompt 09); in
  tests the ``pay`` action is exercised by an admin via ``POST .../mark-paid/``.
- Fulfillment transitions (confirm/ship/deliver) require the order to be PAID,
  and ``complete`` (buyer confirming receipt) requires the item to be DELIVERED.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from .models import Order, OrderItem

# Actor roles ---------------------------------------------------------------
ACTOR_ADMIN = "admin"
ACTOR_BUYER = "buyer"
ACTOR_SELLER = "seller"
ACTOR_PAYMENT = "payment"

# Public-action names (used by serializers/UI to render buttons) ------------
ACTION_CANCEL = "cancel"
ACTION_CONFIRM = "confirm"
ACTION_SHIP = "ship"
ACTION_DELIVER = "deliver"
ACTION_COMPLETE = "complete"
ACTION_MARK_PAID = "mark_paid"
ACTION_FAIL_PAYMENT = "fail_payment"
ACTION_RETRY_PAYMENT = "retry_payment"
ACTION_REFUND = "refund"
ACTION_FORCE_CANCEL = "force_cancel"


class TransitionDenied(Exception):
    """Raised when a status change is not permitted by the state machine."""

    def __init__(self, message: str, code: str = "transition_not_allowed"):
        super().__init__(message)
        self.code = code


def _require_order_paid(item: OrderItem) -> str | None:
    if item.order.status != Order.Status.PAID:
        return "This order is not paid yet; the seller cannot proceed."
    return None


@dataclass(frozen=True)
class Transition:
    action: str
    to: str
    actor: str
    preconditions: tuple[Callable[[object], str | None], ...] = field(default_factory=tuple)

    def precondition_error(self, instance) -> str | None:
        for check in self.preconditions:
            error = check(instance)
            if error:
                return error
        return None


# ---------------------------------------------------------------------------
# Transition tables: (current_status, action) -> Transition
# ---------------------------------------------------------------------------

ORDER_TRANSITIONS: dict[str, dict[str, Transition]] = {
    Order.Status.PENDING_PAYMENT: {
        ACTION_MARK_PAID: Transition(ACTION_MARK_PAID, Order.Status.PAID, ACTOR_PAYMENT),
        ACTION_CANCEL: Transition(ACTION_CANCEL, Order.Status.CANCELLED, ACTOR_BUYER),
        ACTION_FAIL_PAYMENT: Transition(
            ACTION_FAIL_PAYMENT, Order.Status.PAYMENT_FAILED, ACTOR_PAYMENT
        ),
    },
    Order.Status.PAYMENT_FAILED: {
        ACTION_RETRY_PAYMENT: Transition(
            ACTION_RETRY_PAYMENT, Order.Status.PENDING_PAYMENT, ACTOR_PAYMENT
        ),
        ACTION_CANCEL: Transition(ACTION_CANCEL, Order.Status.CANCELLED, ACTOR_BUYER),
    },
    Order.Status.PAID: {
        # Forceful, admin-only exits from the normal fulfillment flow.
        ACTION_REFUND: Transition(ACTION_REFUND, Order.Status.REFUNDED, ACTOR_ADMIN),
        ACTION_FORCE_CANCEL: Transition(ACTION_FORCE_CANCEL, Order.Status.CANCELLED, ACTOR_ADMIN),
    },
}

ITEM_TRANSITIONS: dict[str, dict[str, Transition]] = {
    OrderItem.Status.PENDING: {
        ACTION_CONFIRM: Transition(
            ACTION_CONFIRM,
            OrderItem.Status.CONFIRMED,
            ACTOR_SELLER,
            preconditions=(_require_order_paid,),
        ),
    },
    OrderItem.Status.CONFIRMED: {
        ACTION_SHIP: Transition(
            ACTION_SHIP,
            OrderItem.Status.SHIPPED,
            ACTOR_SELLER,
            preconditions=(_require_order_paid,),
        ),
    },
    OrderItem.Status.SHIPPED: {
        ACTION_DELIVER: Transition(
            ACTION_DELIVER,
            OrderItem.Status.DELIVERED,
            ACTOR_SELLER,
            preconditions=(_require_order_paid,),
        ),
    },
    OrderItem.Status.DELIVERED: {
        # Buyer confirms receipt; completion is the buyer's right.
        ACTION_COMPLETE: Transition(ACTION_COMPLETE, OrderItem.Status.COMPLETED, ACTOR_BUYER),
    },
}

# Item-level cancellation is entered via the order-level flows (buyer pre-payment
# cancel / admin force cancel / refund), not via a public item endpoint, so it is
# intentionally absent from ITEM_TRANSITIONS. Admin force actions are exposed as
# order-level transitions and cascade down to items in services.py.

# Admin can also act as a buyer/seller when the state allows it: admins are
# permitted on any transition (they're the manual/payment stand-in pre-Prompt 09).
_ADMIN_OVERRIDE_ACTORS = frozenset({ACTOR_ADMIN, ACTOR_PAYMENT})


def actor_for_order(user, order=None) -> str | None:
    """Best-fit actor role for *user* relative to an order-level action."""
    if user is None or not user.is_authenticated:
        return None
    if user.is_staff or user.is_superuser:
        return ACTOR_ADMIN
    if order is not None and user == order.buyer:
        return ACTOR_BUYER
    return None


def actor_for_item(user, item: OrderItem) -> str | None:
    """Best-fit actor role for *user* relative to an item-level action."""
    if user is None or not user.is_authenticated:
        return None
    if user.is_staff or user.is_superuser:
        return ACTOR_ADMIN
    if user == item.seller:
        return ACTOR_SELLER
    if user == item.order.buyer:
        return ACTOR_BUYER
    return None


def _transitions_for(instance) -> dict[str, dict[str, Transition]]:
    return ORDER_TRANSITIONS if isinstance(instance, Order) else ITEM_TRANSITIONS


def _current_status(instance) -> str:
    return instance.status if isinstance(instance, Order) else instance.item_status


def get_transition(instance, action: str) -> Transition | None:
    return _transitions_for(instance).get(_current_status(instance), {}).get(action)


def can_transition(user, instance, action: str) -> tuple[bool, str | None]:
    """Check whether *user* may perform *action* on *instance* right now."""
    transition = get_transition(instance, action)
    if transition is None:
        return False, "This transition is not allowed from the current status."

    if isinstance(instance, Order):
        actor = actor_for_order(user, instance)
    else:
        actor = actor_for_item(user, instance)

    if transition.actor in _ADMIN_OVERRIDE_ACTORS:
        if actor not in (ACTOR_ADMIN, ACTOR_PAYMENT):
            return False, "You do not have permission to perform this action."
    elif actor != transition.actor:
        return False, "You do not have permission to perform this action."

    error = transition.precondition_error(instance)
    if error:
        return False, error
    return True, None


def apply_transition(instance, action: str, user=None, *, actor: str | None = None):
    """Validate and apply a transition to *instance* (does not save).

    ``actor`` lets trusted internal callers (payment service, Prompt 09)
    perform payment-related transitions without a request user.
    """
    transition = get_transition(instance, action)
    if transition is None:
        raise TransitionDenied("This transition is not allowed from the current status.")

    acting_actor = actor or _actor_for(instance, user)
    if transition.actor in _ADMIN_OVERRIDE_ACTORS:
        if acting_actor not in (ACTOR_ADMIN, ACTOR_PAYMENT):
            raise TransitionDenied(
                "You do not have permission to perform this action.",
                code="permission_denied",
            )
    elif acting_actor != transition.actor:
        raise TransitionDenied(
            "You do not have permission to perform this action.",
            code="permission_denied",
        )

    precondition_error = transition.precondition_error(instance)
    if precondition_error:
        raise TransitionDenied(precondition_error, code="transition_blocked")

    if isinstance(instance, Order):
        instance.status = transition.to
    else:
        instance.item_status = transition.to
    return instance


def _actor_for(instance, user) -> str | None:
    if user is None or not user.is_authenticated:
        return None
    if isinstance(instance, Order):
        return actor_for_order(user, instance)
    return actor_for_item(user, instance)


def available_actions(instance, user) -> list[dict]:
    """Public list of actions the current user may take on *instance*.

    Used by serializers to tell the UI which buttons to render. Every action
    name matches a POST endpoint under /api/orders/.
    """
    actions = []
    current = _current_status(instance)
    for action, _transition in _transitions_for(instance).get(current, {}).items():
        allowed, _ = can_transition(user, instance, action)
        if allowed:
            actions.append({"action": action, "label": _label(action)})
    return actions


def _label(action: str) -> str:
    labels = {
        ACTION_CANCEL: "Cancel order",
        ACTION_CONFIRM: "Confirm item",
        ACTION_SHIP: "Mark shipped",
        ACTION_DELIVER: "Mark delivered",
        ACTION_COMPLETE: "Confirm receipt",
        ACTION_MARK_PAID: "Mark paid",
        ACTION_RETRY_PAYMENT: "Retry payment",
        ACTION_FAIL_PAYMENT: "Fail payment",
        ACTION_REFUND: "Refund",
        ACTION_FORCE_CANCEL: "Cancel (admin)",
    }
    return labels.get(action, action)
