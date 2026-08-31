"""Model signals: keep one-to-one related records in sync with the user."""

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid="accounts_create_profile")
def create_user_profile(sender, instance, created, **kwargs):
    """Auto-create a Profile (and the user's Wallet) whenever a User is created."""
    if created:
        Profile.objects.create(user=instance)
        # Wallet creation is guarded with get_or_create so the row is never
        # duplicated (e.g. by a re-save of the user in the same request).
        from wallet.models import Wallet

        Wallet.objects.get_or_create(user=instance)
