from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cart", "0008_order_delivery_method"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bank_order_id", models.CharField(max_length=50, unique=True)),
                ("payment_id", models.CharField(blank=True, max_length=128, null=True, unique=True)),
                ("payment_url", models.URLField(blank=True)),
                ("state", models.CharField(choices=[("init_pending", "Init pending"), ("init_unknown", "Init outcome unknown"), ("active", "Active"), ("auth", "Authorized"), ("paid", "Paid"), ("declined", "Declined"), ("canceled", "Canceled"), ("expired", "Expired")], db_index=True, default="init_pending", max_length=20)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payment_attempts", to="cart.order")),
            ],
            options={"ordering": ("-created",)},
        ),
    ]
