from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import MemberProfile, ShippingAddress, SocialConnection


User = get_user_model()


class RegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=40)
    terms_agreed = serializers.BooleanField()
    marketing_agreed = serializers.BooleanField(default=False)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("이미 사용 중인 아이디입니다.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("이미 사용 중인 이메일입니다.")
        return value.lower()

    def validate_phone(self, value):
        if MemberProfile.objects.filter(phone=value).exists():
            raise serializers.ValidationError("이미 사용 중인 휴대폰 번호입니다.")
        return value

    def validate_terms_agreed(self, value):
        if not value:
            raise serializers.ValidationError("필수 약관에 동의해야 합니다.")
        return value

    def validate(self, attrs):
        candidate = User(username=attrs.get("username", ""), email=attrs.get("email", ""))
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        now = timezone.now()
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        MemberProfile.objects.create(
            user=user,
            name=validated_data["name"],
            phone=validated_data["phone"],
            terms_agreed_at=now,
            marketing_agreed=validated_data["marketing_agreed"],
            marketing_agreed_at=now if validated_data["marketing_agreed"] else None,
        )
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if user is None or not user.is_active:
            raise serializers.ValidationError("아이디 또는 비밀번호를 확인해 주세요.")
        attrs["user"] = user
        return attrs


class MemberSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="member_profile.name", default="")
    phone = serializers.CharField(source="member_profile.phone", default="")
    marketing_agreed = serializers.BooleanField(source="member_profile.marketing_agreed", default=False)
    social_connections = serializers.SerializerMethodField()

    def get_social_connections(self, user):
        connected = set(user.social_connections.values_list("provider", flat=True))
        return {provider: provider in connected for provider in SocialConnection.Provider.values}

    class Meta:
        model = User
        fields = ["id", "username", "email", "name", "phone", "marketing_agreed", "social_connections"]


class MemberUpdateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=40)
    marketing_agreed = serializers.BooleanField(required=False)

    def validate_email(self, value):
        user = self.context["request"].user
        if User.objects.exclude(pk=user.pk).filter(email__iexact=value).exists():
            raise serializers.ValidationError("이미 사용 중인 이메일입니다.")
        return value.lower()

    def validate_phone(self, value):
        user = self.context["request"].user
        if MemberProfile.objects.exclude(user=user).filter(phone=value).exists():
            raise serializers.ValidationError("이미 사용 중인 휴대폰 번호입니다.")
        return value

    @transaction.atomic
    def update(self, user, validated_data):
        profile = user.member_profile
        user.email = validated_data["email"]
        user.save(update_fields=["email"])
        profile.name = validated_data["name"]
        profile.phone = validated_data["phone"]
        if "marketing_agreed" in validated_data and profile.marketing_agreed != validated_data["marketing_agreed"]:
            profile.marketing_agreed = validated_data["marketing_agreed"]
            profile.marketing_agreed_at = timezone.now() if profile.marketing_agreed else None
        profile.save(update_fields=["name", "phone", "marketing_agreed", "marketing_agreed_at", "updated_at"])
        return user


class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = [
            "id", "label", "recipient_name", "recipient_phone", "postal_code", "address1",
            "address2", "delivery_memo", "is_default", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        if validated_data.get("is_default") or not user.shipping_addresses.exists():
            user.shipping_addresses.filter(is_default=True).update(is_default=False)
            validated_data["is_default"] = True
        return ShippingAddress.objects.create(user=user, **validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        if validated_data.get("is_default") is False and instance.is_default:
            raise serializers.ValidationError({"is_default": "기본 배송지는 다른 배송지를 기본으로 지정한 뒤 해제할 수 있습니다."})
        if validated_data.get("is_default"):
            instance.user.shipping_addresses.exclude(pk=instance.pk).filter(is_default=True).update(is_default=False)
        return super().update(instance, validated_data)
