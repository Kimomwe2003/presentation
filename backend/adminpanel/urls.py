from django.urls import path

from .views import (
    CategoryCreateView,
    CategoryUpdateView,
    DashboardView,
    ProductAdminListView,
    ProductRemoveView,
    ReportSummaryView,
    UserActivateView,
    UserDetailView,
    UserListView,
    UserSuspendView,
)

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="admin-dashboard"),
    path("reports/summary/", ReportSummaryView.as_view(), name="admin-report-summary"),
    path("users/", UserListView.as_view(), name="admin-user-list"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="admin-user-detail"),
    path("users/<int:pk>/suspend/", UserSuspendView.as_view(), name="admin-user-suspend"),
    path("users/<int:pk>/activate/", UserActivateView.as_view(), name="admin-user-activate"),
    path("products/", ProductAdminListView.as_view(), name="admin-product-list"),
    path("products/<int:pk>/remove/", ProductRemoveView.as_view(), name="admin-product-remove"),
    path("categories/", CategoryCreateView.as_view(), name="admin-category-create"),
    path("categories/<int:pk>/", CategoryUpdateView.as_view(), name="admin-category-update"),
]
