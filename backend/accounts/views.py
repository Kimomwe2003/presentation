"""Authentication and user-profile API views."""

import logging

from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    LoginSerializer,
    PasswordForgotSerializer,
    PasswordResetSerializer,
    RegisterSerializer,
    TokenResponseSerializer,
    UpdateProfileSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        payload = TokenResponseSerializer(
            {"refresh": str(refresh), "access": str(refresh.access_token)}
        ).data
        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=user,
            action=AuditLogService.Action.REGISTER,
            target=user,
            description=f"New account registered: {user.email}",
            request=request,
        )
        return Response(payload, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            from auditlog.services import AuditLogService

            AuditLogService.log(
                actor=None,
                action=AuditLogService.Action.LOGIN_FAILED,
                target=None,
                description=f"Failed login attempt for {request.data.get('email', '')}",
                request=request,
            )
            raise
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        payload = TokenResponseSerializer(
            {"refresh": str(refresh), "access": str(refresh.access_token)}
        ).data
        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=user,
            action=AuditLogService.Action.LOGIN,
            target=user,
            description=f"User logged in: {user.email}",
            request=request,
        )
        return Response(payload)


class PasswordForgotView(APIView):
    """Request a password-reset code.

    Always answers with the same generic payload (never reveals whether the
    email exists). While no SMTP backend is configured, ``DEBUG`` builds
    return the generated code in the response so the mobile app can surface
    it; production must deliver the code out-of-band (email/SMS).
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_password_reset"

    def post(self, request):
        serializer = PasswordForgotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        user = None
        from .models import User

        candidate = User.objects.filter(email=email).first()
        if candidate is not None and candidate.is_active:
            user = candidate

        payload = {
            "detail": "If that email is registered, a reset code has been sent."
        }

        if user is not None:
            from .models import PasswordResetCode

            _, code = PasswordResetCode.issue(user)
            logger.info("Password reset code for %s: %s", user.email, code)
            if settings.DEBUG:
                payload["debug_code"] = code

            from auditlog.services import AuditLogService

            AuditLogService.log(
                actor=user,
                action=AuditLogService.Action.PASSWORD_RESET_REQUESTED,
                target=user,
                description=f"Password reset requested for {user.email}",
                request=request,
            )
        return Response(payload)


class PasswordResetView(APIView):
    """Consume a reset code and set a new password."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_password_reset"

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Invalidate every outstanding session: the old password may have
        # been compromised, so all refresh tokens are unusable now.
        try:
            RefreshToken.for_user(user).blacklist()
        except TokenError:
            pass

        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=user,
            action=AuditLogService.Action.PASSWORD_RESET_COMPLETED,
            target=user,
            description=f"Password reset completed for {user.email}",
            request=request,
        )
        return Response({"detail": "Your password has been reset. You can log in now."})


class LogoutView(APIView):
    """Blacklist the supplied refresh token."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            RefreshToken(refresh_token).blacklist()
        except (TokenError, AttributeError):
            return Response(
                {"detail": "Invalid or already blacklisted refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=request.user,
            action=AuditLogService.Action.LOGOUT,
            target=request.user,
            description=f"User logged out: {request.user.email}",
            request=request,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """Read and update the authenticated user's own profile."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        profile = request.user.profile
        serializer = UpdateProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        before = {
            "full_name": profile.full_name,
            "address": profile.address,
            "phone_number": profile.phone_number,
        }
        serializer.save()
        from auditlog.services import AuditLogService

        AuditLogService.log(
            actor=request.user,
            action=AuditLogService.Action.PROFILE_UPDATE,
            target=profile,
            description=f"Profile updated for {request.user.email}",
            request=request,
            before=before,
            after=serializer.validated_data,
        )
        return Response(UserSerializer(request.user).data)
