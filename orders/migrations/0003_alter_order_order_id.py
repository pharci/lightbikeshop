# Generated by Django 5.0 on 2024-01-04 10:08

import orders.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_remove_orderitem_product_orderitem_product_variant'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='order_id',
            field=models.CharField(default=orders.models.generate_order_id, editable=False, max_length=10, primary_key=True, serialize=False, verbose_name='Номер заказа'),
        ),
    ]
