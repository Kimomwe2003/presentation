from django.urls import path

from .views import (
    WalletBalanceView,
    WalletPendingEarningsView,
    WalletTransactionListView,
)

urlpatterns = [
    path("balance/", WalletBalanceView.as_view(), name="wallet-balance"),
    path(
        "pending-earnings/",
        WalletPendingEarningsView.as_view(),
        name="wallet-pending-earnings",
    ),
    path("transactions/", WalletTransactionListView.as_view(), name="wallet-transactions"),
]
