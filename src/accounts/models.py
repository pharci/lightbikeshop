# accounts/models.py
from __future__ import annotations
import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager

from accounts.otp import sign_with_id

# ===== User =====

class UserManager(BaseUserManager):
    use_in_migrations = True
    def create_user(self, email, **extra):
        if not email: raise ValueError("Email обязателен")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_unusable_password()  # пароль не используем
        user.save(using=self._db)
        return user
    def create_superuser(self, email, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        return self.create_user(email, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name  = models.CharField(max_length=150, blank=True)
    telegram_id = models.CharField(max_length=200, null=True, blank=True)
    telegram_username = models.CharField(max_length=200, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff  = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self): return self.email or f"@{self.telegram_username}" or f"user#{self.pk}"
    

# ===== Email OTP =====

OTP_TTL_SECONDS = 180
OTP_MAX_ATTEMPTS = 5

class EmailOTP(models.Model):
    request_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)

    code_hmac = models.CharField(max_length=64)
    secret_id = models.CharField(max_length=64)

    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=OTP_MAX_ATTEMPTS)

    ip = models.GenericIPAddressField(null=True, blank=True)
    ua = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Заявка OTP (email)"
        verbose_name_plural = "Заявки OTP (email)"
        indexes = [
            models.Index(fields=["email", "created_at"]),
            models.Index(fields=["expires_at"]),
        ]

    @classmethod
    def create_for_email(cls, *, email: str, code: str, secret_id: str, ttl_sec: int = OTP_TTL_SECONDS, **meta):
        now = timezone.now()
        return cls.objects.create(
            email=email,
            code_hmac=sign_with_id(code, secret_id),
            secret_id=secret_id,
            expires_at=now + timedelta(seconds=ttl_sec),
            **meta,
        )

    def can_verify(self) -> bool:
        if self.consumed_at:
            return False
        if timezone.now() > self.expires_at:
            return False
        if self.attempts >= self.max_attempts:
            return False
        return True

    def verify_and_consume(self, code: str) -> bool:
        if not self.can_verify():
            return False
        self.attempts += 1
        ok = self.code_hmac == sign_with_id(code, self.secret_id)
        if ok:
            self.consumed_at = timezone.now()
        self.save(update_fields=["attempts", "consumed_at"])
        return ok