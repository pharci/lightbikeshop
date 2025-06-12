from django.db import models
from django.urls import reverse
# Create your models here.

class Wheel(models.Model):
    image = models.ImageField(upload_to='news-wheel/')
    title = models.CharField(max_length=100)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('products:product_list_by_brand', args=[self.title])