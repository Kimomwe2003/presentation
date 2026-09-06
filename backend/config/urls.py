from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

from media_store.views import serve_media_file
from payments.views import ClickPesaWebhookView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/clickpesa/webhook/", ClickPesaWebhookView.as_view(), name="clickpesa-webhook"),
    path("api/", include("accounts.urls")),
    path("api/", include("catalog.urls")),
    path("api/cart/", include("cart.urls")),
    path("api/orders/", include("orders.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/wallet/", include("wallet.urls")),
    path("api/withdrawals/", include("withdrawals.urls")),
    path("api/chats/", include("chat.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/reviews/", include("reviews.urls")),
    path("api/admin/", include("adminpanel.urls")),
    path("api/", include("auditlog.urls")),
]

# Serve uploaded media from the same Django process in every environment (see
# docs/DEPLOYMENT.md). The view serves from disk first and falls back to the
# durable copy in the media_store database, so images survive redeploys.
urlpatterns += [
    re_path(
        rf"^{settings.MEDIA_URL.lstrip('/')}(?P<path>.*)$",
        serve_media_file,
    ),
]
