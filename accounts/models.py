from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
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


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField('Почта', unique=True)
    username = models.CharField('Имя пользователя', max_length=30, default='Пользователь')
    is_active = models.BooleanField('Активный?', default=True)
    is_staff = models.BooleanField('Персонал?', default=False)
    is_superuser = models.BooleanField('Суперюзер?', default=False)
    last_login = models.DateTimeField('Последний вход', blank=True, null=True)
    created_at = models.DateTimeField('Регистрация', auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def has_perm(self, perm, obj=None):
        return self.is_staff

    def has_module_perms(self, app_label):
        return self.is_staff

    def set_password(self, raw_password):
        
        self.password = make_password(raw_password)
        self.save()

    def check_password(self, raw_password):
        # Проверяем соответствие пароля пользователя
        def setter(raw_password):
            self.set_password(raw_password)
            self.save(update_fields=["password"])

        return check_password(raw_password, self.password, setter)

    def get_username(self):
        # Возвращаем имя пользователя
        return self.email

    @property
    def is_anonymous(self):
        # Проверяем, является ли пользователь анонимным
        return False

    @property
    def is_authenticated(self):
        # Проверяем, аутентифицирован ли пользователь
        return True

    # Другие поля и методы вашей модели User

    def get_orders(self):
        # Получить заказы пользователя
        return Order.objects.filter(user=self)

    def create_order(self, shipping_address, billing_address):
        # Создать заказ
        cart = self.get_cart()
        order = Order.objects.create(user=self, shipping_address=shipping_address, billing_address=billing_address)
        cart.clear()
        return order

    def get_user_by_email(email):
        try:
            user = User.objects.get(email=email)
            return user
        except User.DoesNotExist:
            return None

    def set_unusable_password(self):
        # Установка пароля пользователя как недопустимого для аутентификации
        self.password = make_password(None)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    def __str__(self):
        return f"Уведомление для {self.user.email}"

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'