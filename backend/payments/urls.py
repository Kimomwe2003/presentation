from django.urls import path

from .views import (
    ClickPesaWebhookView,
    PaymentInitiateView,
    PaymentStatusView,
    PaymentVerifyView,
)

urlpatterns = [
    path("initiate/", PaymentInitiateView.as_view(), name="payment-initiate"),
    path("webhook/clickpesa/", ClickPesaWebhookView.as_view(), name="payment-webhook-clickpesa"),
    path("<int:order_id>/status/", PaymentStatusView.as_view(), name="payment-status"),
    path("<int:order_id>/verify/", PaymentVerifyView.as_view(), name="payment-verify"),
]
