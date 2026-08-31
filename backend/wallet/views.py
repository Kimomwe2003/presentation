"""Wallet endpoints (Prompt 10).

- ``GET /api/wallet/balance/``         available balance + lifetime totals
- ``GET /api/wallet/transactions/``    ledger history (paginated, filterable)

Read-only by design: no endpoint accepts a balance or ledger write; money only
moves through ``WalletService`` on verified backend events.
"""

from datetime import date

from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LedgerTransaction
from .serializers import LedgerTransactionSerializer, WalletBalanceSerializer
from .services import WalletService


class WalletBalanceView(APIView):
    """GET /api/wallet/balance/ — current balance + earnings/withdrawal totals."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        summary = WalletService.balance_summary(request.user)
        return Response(WalletBalanceSerializer(summary).data)


class WalletPendingEarningsView(APIView):
    """GET /api/wallet/pending-earnings/ — projected net of sold-but-uncompleted items.

    Serialized as a string (same convention as the balance) so the Decimal
    renders losslessly over JSON.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        pending = WalletService.pending_earnings(request.user)
        return Response({"pending_earnings": str(pending)})


def _parse_date(value: str, param: str, errors: list[str]) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{param} must be an ISO date (YYYY-MM-DD).")
        return None


class WalletTransactionListView(generics.ListAPIView):
    """GET /api/wallet/transactions/ — paginated ledger, filterable.

    Query params:
      type     one of the ledger type codes (credit, debit, platform_fee, ...)
      from     inclusive start date (YYYY-MM-DD)
      to       inclusive end date (YYYY-MM-DD)
    """

    serializer_class = LedgerTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = LedgerTransaction.objects.filter(user=self.request.user)
        type_ = self.request.query_params.get("type")
        if type_:
            qs = qs.filter(type=type_)

        errors: list[str] = []
        raw_from = self.request.query_params.get("from")
        raw_to = self.request.query_params.get("to")
        date_from = _parse_date(raw_from, "from", errors) if raw_from else None
        date_to = _parse_date(raw_to, "to", errors) if raw_to else None
        if errors:
            raise ValidationError({"detail": " ".join(errors)})
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs.select_related("order_item")
