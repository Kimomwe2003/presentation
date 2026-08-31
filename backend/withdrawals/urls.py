from django.urls import path

from .views import (
    WithdrawalAdminPendingView,
    WithdrawalCompleteView,
    WithdrawalFailView,
    WithdrawalListCreateView,
    WithdrawalProcessView,
    WithdrawalRejectView,
)

urlpatterns = [
    path("", WithdrawalListCreateView.as_view(), name="withdrawal-list-create"),
    path("admin/pending/", WithdrawalAdminPendingView.as_view(), name="withdrawal-admin-pending"),
    path("<int:pk>/process/", WithdrawalProcessView.as_view(), name="withdrawal-process"),
    path("<int:pk>/complete/", WithdrawalCompleteView.as_view(), name="withdrawal-complete"),
    path("<int:pk>/fail/", WithdrawalFailView.as_view(), name="withdrawal-fail"),
    path("<int:pk>/reject/", WithdrawalRejectView.as_view(), name="withdrawal-reject"),
]