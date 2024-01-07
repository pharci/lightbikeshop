# Generated by Django 5.0 on 2024-01-04 10:04

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0001_initial'),
        ('store', '0002_attribute_attributevalue'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='orderitem',
            name='product',
        ),
        migrations.AddField(
            model_name='orderitem',
            name='product_variant',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='store.productvariant'),
            preserve_default=False,
        ),
    ]
