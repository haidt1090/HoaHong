from __future__ import annotations

from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, throttling
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.serializers import (
    ChangePasswordSerializer,
    DoctorSignatureSerializer,
    UserInviteSerializer,
    UserProfileUpdateSerializer,
    UserSerializer,
)
from accounts.signatures import (
    clear_signature,
    store_signature_base64,
    store_signature_image,
)
from core.permissions import (
    ROLE_DEPARTMENT_CATEGORY_ACCESS,
    WILDCARD,
    get_editable_department_codes,
)

User = get_user_model()


class LoginThrottle(throttling.AnonRateThrottle):
    scope = "login"


class IsAdmin(permissions.BasePermission):
    """Only allow users with role=admin."""

    def has_permission(self, request: Request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "admin"
        )


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "format": "email"},
                "password": {"type": "string"},
            },
            "required": ["email", "password"],
        }
    },
    responses={
        200: {
            "type": "object",
            "properties": {
                "access": {"type": "string"},
                "refresh": {"type": "string"},
                "user": {"type": "object"},
            },
        }
    },
)
class LoginView(APIView):
    authentication_classes = []  # No session/JWT auth for login — avoid CSRF
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request: Request) -> Response:
        email = request.data.get("email")
        password = request.data.get("password")
        if not email or not password:
            return Response(
                {"detail": "Vui lòng nhập email và mật khẩu."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, email=email, password=password)
        if user is None:
            return Response(
                {"detail": "Email hoặc mật khẩu không đúng."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not user.is_active:
            return Response(
                {"detail": "Tài khoản đã bị vô hiệu hóa."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "refresh": {"type": "string"},
            },
            "required": ["refresh"],
        }
    },
    responses={200: {"type": "object", "properties": {"detail": {"type": "string"}}}},
)
class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request) -> Response:
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token là bắt buộc."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            RefreshToken(refresh_token).blacklist()
        except TokenError:
            return Response(
                {"detail": "Token không hợp lệ hoặc đã bị vô hiệu hóa."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": "Đăng xuất thành công."}, status=status.HTTP_200_OK)


@extend_schema(
    responses={200: UserSerializer},
    request=UserProfileUpdateSerializer,
)
class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(UserSerializer(request.user).data)

    def put(self, request: Request) -> Response:
        serializer = UserProfileUpdateSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)


@extend_schema(
    request=ChangePasswordSerializer,
    responses={200: {"type": "object", "properties": {"detail": {"type": "string"}}}},
)
class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        return Response({"detail": "Đổi mật khẩu thành công."})


@extend_schema(
    request=UserInviteSerializer,
    responses={201: UserSerializer},
)
class UserInviteView(APIView):
    """Admin creates a new user; the user must change password on first login."""

    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request: Request) -> Response:
        serializer = UserInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class DoctorSignatureListView(APIView):
    """List doctors and whether each one has a PNG or a base64 signature."""

    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    @extend_schema(responses={200: DoctorSignatureSerializer(many=True)})
    def get(self, request: Request) -> Response:
        doctors = User.objects.filter(role="doctor", is_active=True).order_by(
            "full_name", "email"
        )
        return Response(DoctorSignatureSerializer(doctors, many=True).data)


class DoctorSignatureDetailView(APIView):
    """Save one doctor's signature as a PNG upload or a base64 string."""

    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _doctor(self, user_id: str) -> User:
        return get_object_or_404(User, pk=user_id, role="doctor")

    @extend_schema(request=None, responses={200: DoctorSignatureSerializer})
    def put(self, request: Request, user_id: str) -> Response:
        doctor = self._doctor(user_id)
        upload = request.FILES.get("signature_image")
        raw_b64 = request.data.get("signature_base64")
        has_b64 = raw_b64 is not None and str(raw_b64).strip() != ""
        if upload and has_b64:
            return Response(
                {"detail": "Chỉ chọn ảnh PNG hoặc chuỗi base64, không gửi cả hai."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            if upload is not None:
                store_signature_image(doctor, upload.read())
            elif has_b64:
                store_signature_base64(doctor, str(raw_b64))
            else:
                return Response(
                    {"detail": "Cần file PNG hoặc chuỗi base64."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValidationError as exc:
            message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(DoctorSignatureSerializer(doctor).data)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, user_id: str) -> Response:
        doctor = self._doctor(user_id)
        clear_signature(doctor)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DoctorSignatureImageView(APIView):
    """PNG preview for admins. The file is stored outside public media."""

    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request: Request, user_id: str) -> FileResponse | Response:
        doctor = get_object_or_404(User, pk=user_id, role="doctor")
        if not doctor.signature_image:
            return Response(status=status.HTTP_404_NOT_FOUND)
        doctor.signature_image.open("rb")
        return FileResponse(doctor.signature_image, content_type="image/png")


@extend_schema(
    responses={
        200: {
            "type": "object",
            "properties": {
                "role": {"type": "string"},
                "all_departments": {"type": "boolean"},
                "editable_department_codes": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "editable_categories": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        }
    },
)
class EditableDepartmentsView(APIView):
    """
    Return which department codes/categories the current user can edit.

    Used by the frontend to lock department tabs the user cannot edit.
    ``all_departments = true`` means the user (doctor/admin) can edit every
    department, so ``editable_department_codes`` will be ``["*"]``.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        role = request.user.role
        codes = get_editable_department_codes(role)
        categories_access = ROLE_DEPARTMENT_CATEGORY_ACCESS.get(role)
        if categories_access == WILDCARD:
            editable_categories: list[str] = [WILDCARD]
        elif categories_access is None:
            editable_categories = []
        else:
            editable_categories = sorted(categories_access)
        return Response(
            {
                "role": role,
                "all_departments": WILDCARD in codes,
                "editable_department_codes": codes,
                "editable_categories": editable_categories,
            }
        )
