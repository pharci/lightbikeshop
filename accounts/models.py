from products.models import Product
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
    email = models.EmailField('Почта', unique=True)
    telegram_id = models.CharField('Telegram Id', max_length=200, null=True, blank=True)
    telegram_username = models.CharField('Telegram Username', max_length=200, null=True, blank=True)
    is_active = models.BooleanField('Активный?', default=True)
    is_staff = models.BooleanField('Персонал?', default=False)
    is_superuser = models.BooleanField('Суперюзер?', default=False)
    last_login = models.DateTimeField('Последний вход', blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def has_perm(self, perm, obj=None):
        return self.is_staff

    def has_module_perms(self, app_label):
        return self.is_staff

    def email_user(self, subject, message, from_email=None, **kwargs):
        # Отправляем электронную почту пользователю
        # Реализуйте логику отправки электронной почты, используя
        # предоставленные аргументы (subject, message, from_email) и
        # дополнительные параметры, если это необходимо
        pass

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


class Order(models.Model):

    STATUS_CHOICES = (
        ('Создан', 'Создан'),
        ('В обработке', 'В обработке'),
        ('В доставке', 'В доставке'),
        ('Готов к выдаче', 'Готов к выдаче'),
        ('Отменен', 'Отменен'),
        ('Завершен', 'Завершен'),
    )

    DELIVERY_CHOICES = (
        ('Почта России', 'Почта России'),
        ('Сдек', 'Сдек'),
        ('Boxberry', 'Boxberry')
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField('Статус', max_length=200, choices=STATUS_CHOICES, default='Создан')
    order_id = models.PositiveIntegerField()
    first_name = models.CharField('Имя', max_length=200, null=False)
    middle_name = models.CharField('Фамилия', max_length=200, null=False)
    last_name = models.CharField('Отчество', max_length=200, null=False, blank=True)
    address = models.CharField('Адрес', max_length=200, null=True, blank=True)
    city = models.CharField('Город', max_length=200, null=True, blank=True)
    phone_number = models.CharField('Телефон', max_length=200, null=False)
    zip_code = models.CharField('Индекс', max_length=200, null=True, blank=True)
    delivery_value = models.CharField('Способ доставки', max_length=200, null=True, blank=True, choices=DELIVERY_CHOICES)
    date_ordered = models.DateTimeField('Дата создания', auto_now_add=True)
    # Другие поля вашей модели Order

    def get_total_price(self):
        orderitems = self.items.all()
        total = sum([item.quantity * item.product.price for item in orderitems])
        return total

    def get_total_count(self):
        orderitems = self.items.all()

        total = sum([item.quantity for item in orderitems])
        return total 

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Товар заказа'
        verbose_name_plural = 'Товары заказов'