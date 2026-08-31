from django.db import transaction
from django.utils import timezone

from cart.models import Cart, CartItem


def get_or_create_cart_for_user(user) -> Cart:
    cart, _ = Cart.objects.get_or_create(
        owner=user,
        defaults={"session_key": None, "expires_at": timezone.now() + timezone.timedelta(days=30)},
    )
    return cart


def get_or_create_anonymous_cart(request) -> Cart:
    session_key = request.session.session_key
    if session_key is None:
        request.session.create()
        session_key = request.session.session_key
    cart = Cart.objects.filter(
        session_key=session_key,
        expires_at__gte=timezone.now(),
    ).first()
    if cart:
        return cart
    cart = Cart.objects.create(
        owner=None,
        session_key=session_key,
        expires_at=timezone.now() + timezone.timedelta(days=30),
    )
    return cart


def get_current_cart(request) -> Cart:
    if request.user.is_authenticated:
        cart = get_or_create_cart_for_user(request.user)
    else:
        cart = get_or_create_anonymous_cart(request)
    from catalog.models import Product
    cart.items.filter(product__status__in=[Product.Status.SOLD, Product.Status.INACTIVE]).delete()
    return cart


def anonymous_cart_items(request):
    session_key = request.session.session_key
    if not session_key:
        return CartItem.objects.none()
    return CartItem.objects.filter(cart__session_key=session_key)


def merge_anonymous_cart_to_user(request) -> None:
    anonymous_items = list(anonymous_cart_items(request))
    if not anonymous_items:
        return
    cart = get_or_create_cart_for_user(request.user)
    anonymous_cart = anonymous_items[0].cart
    with transaction.atomic():
        for item in anonymous_items:
            existing = CartItem.objects.filter(
                cart=cart,
                product=item.product,
                attributes=item.attributes,
            ).first()
            if existing:
                existing.quantity = min(existing.quantity + item.quantity, 100)
                existing.save(update_fields=["quantity"])
            else:
                CartItem.objects.create(
                    cart=cart,
                    product=item.product,
                    quantity=item.quantity,
                    attributes=item.attributes,
                )
        anonymous_cart.delete()
