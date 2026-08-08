from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cart', '0006_alter_order_ms_order_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_id',
            field=models.CharField('T-Bank PaymentId', max_length=128, blank=True, null=True, unique=True),
        ),
    ]
