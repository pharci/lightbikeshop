# Generated by Django 5.0 on 2024-01-15 09:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0007_remove_attributevalue_slug'),
    ]

    operations = [
        migrations.AddField(
            model_name='attributevalue',
            name='value_en',
            field=models.CharField(default='', max_length=100, verbose_name='Значение EN'),
            preserve_default=False,
        ),
    ]
