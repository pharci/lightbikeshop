from django.db import models
from django.urls import reverse

class SliderImage(models.Model):
    image = models.ImageField("Изображение", upload_to='slider_images/')
    caption = models.CharField("Подпись", max_length=200, blank=True)
    order = models.PositiveIntegerField("Порядок", default=0)

    def __str__(self):
        return self.caption or f"Изображение {self.id}"

    class Meta:
        verbose_name = 'Изображение слайдера'
        verbose_name_plural = 'Изображения слайдера'
        ordering = ['order']



class FAQ(models.Model):
    caption = models.CharField("Заголовок", max_length=300)
    text = models.TextField("Ответ")
    order = models.PositiveIntegerField("Порядок", default=0)

    def __str__(self):
        return self.caption

    class Meta:
        verbose_name = 'Часто задаваемый вопрос'
        verbose_name_plural = 'Часто задаваемые вопросы'
        ordering = ['order']