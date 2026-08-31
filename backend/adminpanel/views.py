"""Admin dashboard & moderation endpoints (Prompt 16).

All endpoints require ``IsAdminUser`` (staff or superuser). Aggregations use
efficient ``aggregate``/``annotate`` calls, never per-row loops.

- Dashboard: cross-app stats + recent activity feed.
- Users: list/search, detail (with activity summary), suspend/activate.
- Products: list/search all incl. inactive, remove (deactivate) with a reason.
- Categories: create / update (deactivate) — deferred from Prompt 04.

Moderation "remove" writes a ``reason`` (and deactivates the product) ready for
the Prompt 17 audit log; no separate logging mechanism is built here.
"""

from django.db.models import (
    Avg,
    Case,
    Count,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Profile, User
from catalog.models import Category, Product
from catalog.pagination import CatalogPagination
from orders.models import Order
from payments.models import Payment
from wallet.models import LedgerTransaction, Wallet
from withdrawals.models import WithdrawalRequest

from .serializers import (
    CategoryAdminSerializer,
    ProductAdminSerializer,
    ProductRemoveSerializer,
    UserAdminDetailSerializer,
    UserAdminSerializer,
    UserAdminUpdateSerializer,
)


class IsAdminUser(permissions.BasePermission):
    """Staff or superuser only (kept local so tests exercise our own gate)."""

    message = "Administrator privileges are required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )


def _wallet_balance(user) -> str:
    """Fresh wallet balance for a user (or 0.00 when none exists)."""
    balance = Wallet.objects.filter(user=user).values_list("balance", flat=True).first()
    return str(balance) if balance is not None else "0.00"


class DashboardView(APIView):
    """GET aggregated platform statistics + recent activity feed."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        user_counts = Profile.objects.aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(account_status=Profile.AccountStatus.ACTIVE)),
            suspended=Count("id", filter=Q(account_status=Profile.AccountStatus.SUSPENDED)),
        )
        product_counts = Product.objects.aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(status=Product.Status.ACTIVE)),
        )

        order_counts = dict(
            Order.objects.values("status")
            .annotate(count=Count("id"))
            .values_list("status", "count")
        )

        # Transaction value = money actually collected across successful payments.
        transaction_value = (
            Payment.objects.filter(status=Payment.Status.SUCCESSFUL).aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )
        # Platform fees are stored as negative amounts; report the positive total.
        fees_collected = (
            LedgerTransaction.objects.filter(
                type=LedgerTransaction.Type.PLATFORM_FEE,
                status=LedgerTransaction.Status.COMPLETED,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        withdrawal_counts = WithdrawalRequest.objects.aggregate(
            pending=Count("id", filter=Q(status=WithdrawalRequest.Status.PENDING)),
            processing=Count("id", filter=Q(status=WithdrawalRequest.Status.PROCESSING)),
            completed=Count("id", filter=Q(status=WithdrawalRequest.Status.COMPLETED)),
        )
        failed_payments = Payment.objects.filter(
            status=Payment.Status.FAILED
        ).count()

        recent = self._activity_feed()

        return Response(
            {
                "users": {
                    "total": user_counts["total"],
                    "active": user_counts["active"],
                    "suspended": user_counts["suspended"],
                },
                "products": {
                    "total": product_counts["total"],
                    "active": product_counts["active"],
                },
                "orders_by_status": order_counts,
                "order_total": sum(order_counts.values()),
                "transaction_value": str(transaction_value),
                "platform_fees_collected": str(abs(fees_collected)),
                "withdrawals": {
                    "pending": withdrawal_counts["pending"],
                    "processing": withdrawal_counts["processing"],
                    "completed": withdrawal_counts["completed"],
                },
                "failed_payments": failed_payments,
                "recent_activity": recent,
            }
        )

    @staticmethod
    def _activity_feed(limit: int = 12) -> list[dict]:
        """A few recent cross-app events, newest first.

        Combines recent orders, reviews and withdrawals. Each entry is
        self-describing so the client renders it generically.
        """
        feed: list[dict] = []
        orders = Order.objects.select_related("buyer", "buyer__profile").order_by(
            "-placed_at"
        )[:5]
        for order in orders:
            feed.append(
                {
                    "type": "order",
                    "message": f"Order {order.order_number} → {order.get_status_display()}",
                    "created_at": order.placed_at,
                }
            )

        from reviews.models import Review

        reviews = Review.objects.select_related("buyer", "product").order_by(
            "-created_at"
        )[:5]
        for review in reviews:
            name = None
            full_name = review.buyer.profile.full_name
            if full_name:
                name = full_name
            else:
                name = review.buyer.email
            feed.append(
                {
                    "type": "review",
                    "message": f"{name} rated {review.product.name} {review.rating}/5",
                    "created_at": review.created_at,
                }
            )

        withdrawals = WithdrawalRequest.objects.select_related("user").order_by(
            "-created_at"
        )[:5]
        for wd in withdrawals:
            feed.append(
                {
                    "type": "withdrawal",
                    "message": (
                        f"Withdrawal {wd.reference} {wd.amount} → "
                        f"{wd.get_status_display()}"
                    ),
                    "created_at": wd.created_at,
                }
            )

        feed.sort(key=lambda e: e["created_at"], reverse=True)
        return feed[:limit]


class UserListView(generics.ListAPIView):
    """GET list/search users (staff only)."""

    permission_classes = [IsAdminUser]
    serializer_class = UserAdminSerializer
    pagination_class = CatalogPagination
    filter_backends = [SearchFilter]
    search_fields = ["email", "username", "profile__full_name"]

    def get_queryset(self):
        return (
            User.objects.select_related("profile")
            .annotate(
                is_suspended=Case(
                    When(
                        profile__account_status=Profile.AccountStatus.SUSPENDED,
                        then=Value(True),
                    ),
                    default=Value(False),
                )
            )
            .order_by("-date_joined", "id")
        )


class UserDetailView(APIView):
    """Admin management of a single member account (staff only).

    - ``GET``: full detail incl. activity summary and wallet balance.
    - ``PATCH``: edit profile fields (email, full name, phone, address, role).
    - ``DELETE``: permanently remove the account (admin accounts are protected).
    """

    permission_classes = [IsAdminUser]

    @staticmethod
    def _get_user(pk):
        return get_object_or_404(User.objects.select_related("profile"), pk=pk)

    def get(self, request, pk):
        user = self._get_user(pk)
        data = UserAdminDetailSerializer(user).data
        data["product_count"] = user.products.count()
        data["order_count"] = user.orders.count()
        data["sold_count"] = user.sold_items.count()
        data["wallet_balance"] = _wallet_balance(user)
        return Response(data)

    def patch(self, request, pk):
        user = self._get_user(pk)
        if user.is_staff or user.is_superuser:
            return Response(
                {"detail": "Administrator accounts cannot be edited."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = UserAdminUpdateSerializer(
            user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        profile = getattr(user, "profile", None)
        before = {
            "email": user.email,
            "full_name": profile.full_name if profile is not None else "",
        }
        serializer.save()
        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=request.user,
            action=AuditLogService.Action.USER_UPDATE,
            target=user,
            description=f"User {user.email} updated by {request.user.email}",
            request=request,
            before=before,
            after=serializer.validated_data,
        )
        return Response(UserAdminDetailSerializer(user).data)

    def delete(self, request, pk):
        user = self._get_user(pk)
        if user.is_staff or user.is_superuser:
            return Response(
                {"detail": "Administrator accounts cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.pk == request.user.pk:
            return Response(
                {"detail": "You cannot delete your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        email = user.email
        profile = getattr(user, "profile", None)
        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=request.user,
            action=AuditLogService.Action.USER_DELETE,
            target=user,
            description=f"User {email} deleted by {request.user.email}",
            request=request,
            before={"email": email},
        )
        if profile is not None:
            Profile.objects.filter(pk=profile.pk).update(account_status=Profile.AccountStatus.SUSPENDED)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserSuspendView(APIView):
    """POST suspend a user: set Profile.account_status = SUSPENDED.

    The Prompt 02 login check rejects any non-ACTIVE account, so a suspended
    user immediately loses login capability.
    """

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.is_staff or user.is_superuser:
            return Response(
                {"detail": "Administrators cannot be suspended."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile = user.profile
        profile.account_status = Profile.AccountStatus.SUSPENDED
        profile.save(update_fields=["account_status", "updated_at"])
        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=request.user,
            action=AuditLogService.Action.USER_SUSPEND,
            target=user,
            description=f"User {user.email} suspended by {request.user.email}",
            request=request,
            after={"account_status": profile.account_status},
        )
        return Response({"id": user.pk, "suspended": True})


class UserActivateView(APIView):
    """POST reactivate a suspended user."""

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        profile = user.profile
        profile.account_status = Profile.AccountStatus.ACTIVE
        profile.save(update_fields=["account_status", "updated_at"])
        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=request.user,
            action=AuditLogService.Action.USER_ACTIVATE,
            target=user,
            description=f"User {user.email} activated by {request.user.email}",
            request=request,
            after={"account_status": profile.account_status},
        )
        return Response({"id": user.pk, "suspended": False})


class ProductAdminListView(generics.ListAPIView):
    """GET list/search all products including inactive (staff only)."""

    permission_classes = [IsAdminUser]
    serializer_class = ProductAdminSerializer
    pagination_class = CatalogPagination
    filter_backends = [SearchFilter]
    search_fields = ["name", "description", "seller__email", "category__name"]

    def get_queryset(self):
        return (
            Product.objects.select_related("seller", "seller__profile", "category")
            .prefetch_related("images")
            .annotate(
                avg_rating=Avg("reviews__rating"),
                review_count=Count("reviews"),
            )
            .order_by("-created_at", "-id")
        )


class ProductRemoveView(APIView):
    """POST force-deactivate a product with a required reason.

    Soft removal: sets status to INACTIVE (hidden from public listings) and
    records the reason (consumed by the Prompt 17 audit log). No competing log
    mechanism is introduced.
    """

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        serializer = ProductRemoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]

        product.status = Product.Status.INACTIVE
        product.save(update_fields=["status", "updated_at"])

        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=request.user,
            action=AuditLogService.Action.PRODUCT_REMOVE,
            target=product,
            description=f"Product {product.name} removed by {request.user.email}",
            request=request,
            after={"status": product.status, "reason": reason},
        )

        return Response(
            {
                "id": product.pk,
                "status": product.status,
                "reason": reason,
                "removed": True,
            }
        )


class CategoryCreateView(generics.CreateAPIView):
    """POST create a category (staff only)."""

    permission_classes = [IsAdminUser]
    serializer_class = CategoryAdminSerializer
    queryset = Category.objects.all()

    def perform_create(self, serializer):
        category = serializer.save()
        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=self.request.user,
            action=AuditLogService.Action.CATEGORY_CREATE,
            target=category,
            description=f"Category {category.name} created",
            request=self.request,
            after={"name": category.name, "slug": category.slug},
        )


class CategoryUpdateView(generics.UpdateAPIView):
    """PATCH update a category (rename / move / deactivate)."""

    permission_classes = [IsAdminUser]
    serializer_class = CategoryAdminSerializer
    queryset = Category.objects.all()

    def perform_update(self, serializer):
        category = self.get_object()
        before = {
            "name": category.name,
            "slug": category.slug,
            "parent": category.parent_id,
            "is_active": category.is_active,
        }
        category = serializer.save()
        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=self.request.user,
            action=AuditLogService.Action.CATEGORY_UPDATE,
            target=category,
            description=f"Category {category.name} updated",
            request=self.request,
            before=before,
            after={
                "name": category.name,
                "slug": category.slug,
                "parent": category.parent_id,
                "is_active": category.is_active,
            },
        )


class ReportSummaryView(APIView):
    """GET /api/admin/reports/summary/ — aggregate platform reporting.

    Builds on the Prompt 16 dashboard with time-series figures computed
    server-side:
    - daily transaction volume (sum of SUCCESSFUL payments per day)
    - fee revenue over time (sum of PLATFORM_FEE ledger rows per day, abs value)
    - new users over time (registrations per day)

    ``?days=`` (default 30) controls the window. All figures are aggregate()
    calls over indexed columns — no per-row loops.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        from datetime import timedelta

        from django.utils import timezone

        days = 30
        try:
            days = int(request.query_params.get("days", 30))
        except (TypeError, ValueError):
            days = 30
        days = max(1, min(days, 365))
        since = timezone.now() - timedelta(days=days)

        # Daily transaction volume (money actually collected).
        transaction_volume = list(
            Payment.objects.filter(
                status=Payment.Status.SUCCESSFUL, created_at__gte=since
            )
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Sum("amount"))
            .order_by("day")
        )

        # Fee revenue over time (platform fees, stored negative → abs).
        fee_revenue = list(
            LedgerTransaction.objects.filter(
                type=LedgerTransaction.Type.PLATFORM_FEE,
                status=LedgerTransaction.Status.COMPLETED,
                created_at__gte=since,
            )
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Sum("amount"))
            .order_by("day")
        )

        # New users over time (daily registrations).
        new_users = list(
            User.objects.filter(date_joined__gte=since)
            .annotate(day=TruncDate("date_joined"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )

        return Response(
            {
                "days": days,
                "transaction_volume": [
                    {"date": row["day"], "total": str(row["total"] or 0)}
                    for row in transaction_volume
                ],
                "fee_revenue": [
                    {"date": row["day"], "total": str(abs(row["total"] or 0))}
                    for row in fee_revenue
                ],
                "new_users": [
                    {"date": row["day"], "count": row["count"]}
                    for row in new_users
                ],
            }
        )
