from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    LoginView,
    LogoutView,
    MeView,
    PasswordForgotView,
    PasswordResetView,
    RegisterView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/password/forgot/", PasswordForgotView.as_view(), name="password-forgot"),
    path("auth/password/reset/", PasswordResetView.as_view(), name="password-reset"),
    path("users/me/", MeView.as_view(), name="me"),
]
