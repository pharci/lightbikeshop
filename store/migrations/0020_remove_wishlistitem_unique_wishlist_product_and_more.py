# Generated by Django 5.0.1 on 2024-07-09 12:44

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0019_wishlistitem_alter_wishlist_options_and_more'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='wishlistitem',
            name='unique_wishlist_product',
        ),
        migrations.AlterField(
            model_name='attributevalue',
            name='value',
            field=models.CharField(max_length=100, verbose_name='Значение (Отображаемое)'),
        ),
        migrations.AlterField(
            model_name='attributevalue',
            name='value_en',
            field=models.CharField(blank=True, max_length=100, verbose_name='Значение EN (Серверное)'),
        ),
        migrations.AlterField(
            model_name='attributevariant',
            name='value',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attribute_variants', to='store.attributevalue', verbose_name='Значение'),
        ),
    ]
