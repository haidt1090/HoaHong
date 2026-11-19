import base64

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

User = get_user_model()


class AuthApiTests(APITestCase):
    def setUp(self) -> None:
        cache.clear()
        self.password = "StrongPass123!"
        self.user = User.objects.create_user(
            email="doctor@example.com",
            password=self.password,
            full_name="Doctor User",
            role="doctor",
            must_change_password=True,
        )

    def test_login_returns_tokens_and_user_metadata(self) -> None:
        response = self.client.post(
            reverse("accounts:login"),
            {"email": self.user.email, "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertIn("access", body)
        self.assertIn("refresh", body)
        self.assertEqual(body["user"]["email"], self.user.email)
        self.assertEqual(body["user"]["role"], "doctor")
        self.assertTrue(body["user"]["must_change_password"])

    def test_login_invalid_credentials(self) -> None:
        response = self.client.post(
            reverse("accounts:login"),
            {"email": self.user.email, "password": "wrong"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_returns_new_access_token(self) -> None:
        login_response = self.client.post(
            reverse("accounts:login"),
            {"email": self.user.email, "password": self.password},
            format="json",
        )
        refresh = login_response.json()["refresh"]

        response = self.client.post(
            reverse("accounts:token_refresh"),
            {"refresh": refresh},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.json())

    def test_logout_blacklists_refresh_token(self) -> None:
        login_response = self.client.post(
            reverse("accounts:login"),
            {"email": self.user.email, "password": self.password},
            format="json",
        )
        body = login_response.json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['access']}")

        response = self.client.post(
            reverse("accounts:logout"),
            {"refresh": body["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(BlacklistedToken.objects.count(), 1)

    def test_logout_reused_token_fails(self) -> None:
        login_response = self.client.post(
            reverse("accounts:login"),
            {"email": self.user.email, "password": self.password},
            format="json",
        )
        body = login_response.json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['access']}")

        # First logout succeeds
        self.client.post(
            reverse("accounts:logout"),
            {"refresh": body["refresh"]},
            format="json",
        )

        # Reuse blacklisted token
        response = self.client.post(
            reverse("accounts:logout"),
            {"refresh": body["refresh"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_current_user_get(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("accounts:current_user"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["email"], self.user.email)
        self.assertEqual(response.json()["role"], "doctor")

    def test_current_user_update_profile(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            reverse("accounts:current_user"),
            {"full_name": "Updated Name", "phone": "0909123456"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Updated Name")
        self.assertEqual(self.user.phone, "0909123456")

    def test_change_password_clears_must_change_password(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("accounts:change_password"),
            {
                "old_password": self.password,
                "new_password": "NewStrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertTrue(self.user.check_password("NewStrongPass123!"))

    def test_change_password_wrong_old_password(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("accounts:change_password"),
            {
                "old_password": "wrong",
                "new_password": "NewStrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_throttled_after_failed_attempts(self) -> None:
        url = reverse("accounts:login")

        last_response = None
        for _ in range(6):
            last_response = self.client.post(
                url,
                {"email": self.user.email, "password": "wrong-password"},
                format="json",
            )

        self.assertIsNotNone(last_response)
        self.assertEqual(last_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_admin_can_invite_user(self) -> None:
        admin = User.objects.create_user(
            email="admin@example.com",
            password="AdminPass123!",
            full_name="Admin User",
            role="admin",
        )
        self.client.force_authenticate(user=admin)

        response = self.client.post(
            reverse("accounts:user_invite"),
            {
                "email": "nurse@example.com",
                "password": "TempPass123!",
                "full_name": "Nurse User",
                "phone": "0909000000",
                "role": "nurse",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        invited_user = User.objects.get(email="nurse@example.com")
        self.assertTrue(invited_user.must_change_password)
        self.assertTrue(invited_user.check_password("TempPass123!"))

    def test_non_admin_cannot_invite_user(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("accounts:user_invite"),
            {
                "email": "blocked@example.com",
                "password": "TempPass123!",
                "full_name": "Blocked User",
                "role": "nurse",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_access_to_me_is_denied(self) -> None:
        response = self.client.get(reverse("accounts:current_user"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_swagger_docs_accessible(self) -> None:
        response = self.client.get(reverse("swagger-ui"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_schema_accessible(self) -> None:
        response = self.client.get(reverse("schema"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class DoctorSignatureApiTests(APITestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_user(
            email="sig-admin@example.com",
            password="AdminPass123!",
            full_name="Admin",
            role="admin",
        )
        self.doctor = User.objects.create_user(
            email="sig-doctor@example.com",
            password="DoctorPass123!",
            full_name="Bác sĩ A",
            role="doctor",
        )
        self.client.force_authenticate(user=self.admin)

    def tearDown(self) -> None:
        self.doctor.refresh_from_db()
        if self.doctor.signature_image:
            self.doctor.signature_image.delete(save=False)

    def test_list_includes_doctor_without_signature(self) -> None:
        response = self.client.get(reverse("accounts:doctor_signature_list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = next(
            item for item in response.json() if item["id"] == str(self.doctor.id)
        )
        self.assertEqual(row["signature_kind"], "")

    def test_upload_png_then_preview(self) -> None:
        upload = SimpleUploadedFile("sign.png", _PNG, content_type="image/png")
        response = self.client.put(
            reverse("accounts:doctor_signature_detail", args=[self.doctor.id]),
            {"signature_image": upload},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["signature_kind"], "image")
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.signature_base64, "")

        image = self.client.get(
            reverse("accounts:doctor_signature_image", args=[self.doctor.id])
        )
        self.assertEqual(image.status_code, status.HTTP_200_OK)
        self.assertEqual(image["Content-Type"], "image/png")
        self.assertEqual(b"".join(image.streaming_content), _PNG)

    def test_paste_base64_replaces_image(self) -> None:
        upload = SimpleUploadedFile("sign.png", _PNG, content_type="image/png")
        self.client.put(
            reverse("accounts:doctor_signature_detail", args=[self.doctor.id]),
            {"signature_image": upload},
            format="multipart",
        )
        payload = "data:image/png;base64," + base64.b64encode(b"cks").decode()
        response = self.client.put(
            reverse("accounts:doctor_signature_detail", args=[self.doctor.id]),
            {"signature_base64": payload},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["signature_kind"], "base64")
        self.doctor.refresh_from_db()
        self.assertFalse(self.doctor.signature_image)
        self.assertEqual(
            self.doctor.signature_base64, base64.b64encode(b"cks").decode()
        )

    def test_reject_non_png(self) -> None:
        upload = SimpleUploadedFile("sign.jpg", b"not-a-png", content_type="image/jpeg")
        response = self.client.put(
            reverse("accounts:doctor_signature_detail", args=[self.doctor.id]),
            {"signature_image": upload},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_doctor_cannot_manage_signatures(self) -> None:
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get(reverse("accounts:doctor_signature_list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_png_falls_back_instead_of_raising(self) -> None:
        from accounts.signatures import signature_base64_for_sync

        self.doctor.signature_image.name = f"{self.doctor.pk}.png"
        stored = base64.b64encode(b"fallback").decode()
        self.doctor.signature_base64 = stored
        self.doctor.save(update_fields=["signature_image", "signature_base64"])

        self.assertEqual(signature_base64_for_sync(self.doctor), stored)

        self.doctor.signature_base64 = ""
        self.doctor.save(update_fields=["signature_base64"])
        self.assertEqual(signature_base64_for_sync(self.doctor), "")

    def test_delete_clears_signature(self) -> None:
        self.client.put(
            reverse("accounts:doctor_signature_detail", args=[self.doctor.id]),
            {"signature_base64": base64.b64encode(b"cks").decode()},
            format="json",
        )
        response = self.client.delete(
            reverse("accounts:doctor_signature_detail", args=[self.doctor.id])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.signature_base64, "")
