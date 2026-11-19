from __future__ import annotations

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import (
    ChangePasswordView,
    CurrentUserView,
    DoctorSignatureDetailView,
    DoctorSignatureImageView,
    DoctorSignatureListView,
    EditableDepartmentsView,
    LoginView,
    LogoutView,
    UserInviteView,
)

app_name = "accounts"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", CurrentUserView.as_view(), name="current_user"),
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),
    path(
        "me/editable-departments/",
        EditableDepartmentsView.as_view(),
        name="editable_departments",
    ),
    path("users/invite/", UserInviteView.as_view(), name="user_invite"),
    path(
        "doctor-signatures/",
        DoctorSignatureListView.as_view(),
        name="doctor_signature_list",
    ),
    path(
        "doctor-signatures/<uuid:user_id>/",
        DoctorSignatureDetailView.as_view(),
        name="doctor_signature_detail",
    ),
    path(
        "doctor-signatures/<uuid:user_id>/image/",
        DoctorSignatureImageView.as_view(),
        name="doctor_signature_image",
    ),
]
