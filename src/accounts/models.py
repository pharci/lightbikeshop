from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.contrib.auth.hashers import make_password, check_password
from django.db import models

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)  # Устанавливаем реальный пароль
        else:
            user.set_unusable_password()  # Устанавливаем недопустимый пароль
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser):
    id = models.AutoField(primary_key=True)
    email = models.EmailField('Почта', unique=True, null=True, blank=True)
    telegram_id = models.CharField('Telegram Id', max_length=200, null=True, blank=True)
    telegram_username = models.CharField('Telegram Username', max_length=200, null=True, blank=True)
    is_active = models.BooleanField('Активный?', default=True)
    is_staff = models.BooleanField('Персонал?', default=False)
    is_superuser = models.BooleanField('Суперюзер?', default=False)
    last_login = models.DateTimeField('Последний вход', blank=True, null=True)
    password = models.CharField("Пароль", max_length=128, blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def save(self, *args, **kwargs):
        if self.password and not self.password.startswith("pbkdf2_"):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def has_perm(self, perm, obj=None):
        return self.is_staff

    def has_module_perms(self, app_label):
        return self.is_staff

    def set_password(self, raw_password):
        self.password = make_password(raw_password)
        self.save()

    def check_password(self, raw_password):
        if not self.password:  # None или пустая строка → пароля нет
            return False

        def setter(raw_password):
            self.set_password(raw_password)
            self.save(update_fields=["password"])

        return check_password(raw_password, self.password, setter)

    def get_username(self):
        return self.email

    @property
    def is_anonymous(self):
        return False

    @property
    def is_authenticated(self):
        return True

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        if self.email:
            return self.email
        if self.telegram_username:
            return f"@{self.telegram_username}"
        if self.telegram_id:
            return f"tg_id:{self.telegram_id}"
        return f"user#{self.id}"