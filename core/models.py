from django.db import models
from django.urls import reverse


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