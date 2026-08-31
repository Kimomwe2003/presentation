"""Withdrawal endpoints (Prompt 12).

User-facing:
- ``POST /api/withdrawals/``            create a payout request
- ``GET  /api/withdrawals/``            list the caller's own requests

Admin-facing (staff only):
- ``GET  /api/withdrawals/admin/pending/``  admin processing queue
- ``POST /api/withdrawals/{id}/process/``   PENDING -> PROCESSING
- ``POST /api/withdrawals/{id}/complete/``  PROCESSING -> COMPLETED
- ``POST /api/withdrawals/{id}/fail/``      PROCESSING -> FAILED (refund)
- ``POST /api/withdrawals/{id}/reject/``    PENDING/PROCESSING -> REJECTED (refund)

Admin action bodies accept an optional ``admin_notes`` string.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import WithdrawalRequest
from .serializers import WithdrawalCreateSerializer, WithdrawalRequestSerializer
from .services import TransitionDenied, WithdrawalService


def _transition_error_response(exc: TransitionDenied) -> Response:
    code = 403 if exc.code == "permission_denied" else 400
    return Response({"detail": str(exc)}, status=code)


class WithdrawalListCreateView(generics.ListCreateAPIView):
    """GET own requests + POST a new payout request."""

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WithdrawalRequest.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return WithdrawalCreateSerializer
        return WithdrawalRequestSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.create(serializer.validated_data)
        out = WithdrawalRequestSerializer(instance)
        return Response(out.data, status=status.HTTP_201_CREATED)


class WithdrawalAdminPendingView(generics.ListAPIView):
    """GET the admin queue: all non-terminal requests, oldest first."""

    permission_classes = [permissions.IsAdminUser]
    serializer_class = WithdrawalRequestSerializer

    def get_queryset(self):
        return (
            WithdrawalRequest.objects.filter(
                Q(status=WithdrawalRequest.Status.PENDING)
                | Q(status=WithdrawalRequest.Status.PROCESSING)
            )
            .select_related("user")
            .order_by("created_at", "id")
        )


class WithdrawalActionView(APIView):
    """Base for admin lifecycle actions (process/complete/fail/reject)."""

    permission_classes = [permissions.IsAdminUser]
    #: Overridden by subclasses.
    action_name: str = ""

    def get_request(self, pk: int) -> WithdrawalRequest:
        return get_object_or_404(WithdrawalRequest, pk=pk)

    def post(self, request, pk: int):
        instance = self.get_request(pk)
        admin_notes = request.data.get("admin_notes", "")
        try:
            updated = WithdrawalService.transition(
                instance,
                to=self.action_name,
                actor=request.user,
                admin_notes=admin_notes,
            )
        except TransitionDenied as exc:
            return _transition_error_response(exc)
        return Response(WithdrawalRequestSerializer(updated).data)


class WithdrawalProcessView(WithdrawalActionView):
    action_name = WithdrawalRequest.Status.PROCESSING


class WithdrawalCompleteView(WithdrawalActionView):
    action_name = WithdrawalRequest.Status.COMPLETED


class WithdrawalFailView(WithdrawalActionView):
    action_name = WithdrawalRequest.Status.FAILED


class WithdrawalRejectView(WithdrawalActionView):
    action_name = WithdrawalRequest.Status.REJECTED