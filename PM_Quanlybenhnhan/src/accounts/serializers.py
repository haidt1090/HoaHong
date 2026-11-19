from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.models import Company

User = get_user_model()


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "name", "code"]
        read_only_fields = ["id"]


class DoctorSignatureSerializer(serializers.ModelSerializer):
    """Doctor row for the signature admin screen. The payload itself is not returned."""

    signature_kind = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "full_name", "email", "signature_kind"]

    def get_signature_kind(self, obj: User) -> str:
        from accounts.signatures import signature_kind

        return signature_kind(obj)


class UserSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "phone",
            "role",
            "is_active",
            "must_change_password",
            "company",
        ]
        read_only_fields = ["id", "email", "role", "is_active", "must_change_password"]


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["full_name", "phone"]

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save(update_fields=list(validated_data.keys()))
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value: str) -> str:
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Mật khẩu cũ không đúng.")
        return value

    def validate_new_password(self, value: str) -> str:
        validate_password(value)
        return value


class UserInviteSerializer(serializers.ModelSerializer):
    """Serializer for admin to create/invite a new user."""

    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "phone", "role", "password", "company"]
        read_only_fields = ["id"]

    def validate_role(self, value: str) -> str:
        valid_roles = [r[0] for r in User.ROLE_CHOICES]
        if value not in valid_roles:
            raise serializers.ValidationError(
                f"Role phải là một trong: {', '.join(valid_roles)}"
            )
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.must_change_password = True
        user.save()
        return user
