# Generated by Django 5.0 on 2024-01-06 07:46

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0002_attribute_attributevalue'),
    ]

    operations = [
        migrations.CreateModel(
            name='Inventory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stock_level', models.IntegerField(default=0, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Количество')),
                ('low_stock_threshold', models.PositiveIntegerField(default=5, verbose_name='Порог низкого запаса')),
                ('low_stock_alert', models.BooleanField(default=False, verbose_name='На исходе')),
                ('product_variant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='inventory', to='store.productvariant')),
            ],
            options={
                'verbose_name': 'Инвентарь',
                'verbose_name_plural': 'Инвентарь',
            },
        ),
    ]
