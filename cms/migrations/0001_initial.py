# Generated by Django 5.0 on 2024-01-04 08:52

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='FAQ',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('caption', models.CharField(max_length=300, verbose_name='Заголовок')),
                ('answer', models.TextField(verbose_name='Ответ')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Порядок')),
            ],
            options={
                'verbose_name': 'Часто задаваемый вопрос',
                'verbose_name_plural': 'Часто задаваемые вопросы',
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='SliderImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='slider_images/', verbose_name='Изображение')),
                ('caption', models.CharField(blank=True, max_length=200, verbose_name='Подпись')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Порядок')),
            ],
            options={
                'verbose_name': 'Изображение слайдера',
                'verbose_name_plural': 'Изображения слайдера',
                'ordering': ['order'],
            },
        ),
    ]
