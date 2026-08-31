from django.db import models
from django.db.models import Sum


class CartQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def not_expired(self):
        from django.utils import timezone

        return self.filter(expires_at__gte=timezone.now())


class CartItemQuerySet(models.QuerySet):
    def active(self):
        return self.filter(cart__is_active=True)

    def quantities(self):
        return self.values("product_id").annotate(total=Sum("quantity"))


class CartManager(models.Manager.from_queryset(CartQuerySet)):
    pass


class CartItemManager(models.Manager.from_queryset(CartItemQuerySet)):
    pass
