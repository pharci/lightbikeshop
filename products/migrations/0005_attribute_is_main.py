# Generated by Django 5.0 on 2023-12-31 06:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0004_productvariant_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='attribute',
            name='is_main',
            field=models.BooleanField(default=False, verbose_name='Отображать в названии'),
        ),
    ]
