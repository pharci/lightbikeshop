from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cart", "0007_order_payment_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="delivery_method",
            field=models.CharField("Способ получения", max_length=32, blank=True, default=""),
        ),
    ]
