from django.db import models
from django.urls import reverse
from django.core.validators import URLValidator

class SocialLink(models.Model):
    title = models.CharField(max_length=50)           # название: VK, YouTube
    url = models.URLField()                           # ссылка
    icon = models.ImageField(upload_to="social/")     # иконка
    order = models.PositiveIntegerField(default=0)    # порядок

    class Meta:
        verbose_name = "Социальные сети"
        verbose_name_plural = "Социальные сети"
        ordering = ("order",)

    def __str__(self):
        return self.title

class Wheel(models.Model):
    title = models.CharField("Заголовок", max_length=100)
    image = models.ImageField("Изображение", upload_to="wheel/")
    url = models.URLField("Ссылка", blank=True)

    is_active = models.BooleanField("Активен", default=True)
    order = models.PositiveIntegerField("Порядок", default=0, db_index=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return self.url or "#"

    class Meta:
        verbose_name = "Колесо"
        verbose_name_plural = "Колесо"
        ordering = ("order",)


class FAQ(models.Model):
    title = models.CharField("Заголовок", max_length=200)
    content = models.TextField("Содержимое")
    color = models.CharField("Цвет флажка (css-класс или hex)", max_length=32, default="faq-chip--gray")
    order = models.PositiveIntegerField("Порядок", default=0, db_index=True)
    is_active = models.BooleanField("Активен", default=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ("order",)
        verbose_name = "FAQ блок"
        verbose_name_plural = "FAQ блоки"


validate_url_ext = URLValidator(schemes=["http", "https", "mailto", "tel"])

class Page(models.Model):
    COLS = [(1, "Соцсети"), (2, "Контакты"), (3, "Информация"), (4, "Помощь")]

    slug = models.SlugField(unique=True, max_length=120)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)  # контент страницы
    column = models.PositiveSmallIntegerField(choices=COLS, null=True, blank=True)  # номер колонки футера
    order = models.PositiveIntegerField(default=0)  # порядок в колонке
    is_published = models.BooleanField(default=True)

    external_url = models.URLField("Ссылка", blank=True, validators=[validate_url_ext])
    anchor = models.CharField(max_length=120, blank=True)  # напр. "faq-chapter-1"

    class Meta:
        verbose_name = "Страницы футера"
        verbose_name_plural = "Страницы футера"
        ordering = ("column", "order", "title")

    def get_absolute_url(self):
        if self.external_url:
            return self.external_url
        url = reverse("core:detail", args=[self.slug])
        return f"{url}#{self.anchor}" if self.anchor else url

    def __str__(self):
        return self.title
    

