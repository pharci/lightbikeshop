from django.db import migrations, models


KEYS = [
    "CDEK_ID", "CDEK_SECRET", "CDEK_SENDER_CODE", "YANDEX_MAPS_API_KEY",
    "DADATA_TOKEN", "T_BANK_TERMINAL_KEY", "T_BANK_PASSWORD", "MOYSKLAD_TOKEN",
    "MOYSKLAD_ORGANIZATION_ID", "MOYSKLAD_STORE_ID", "MOYSKLAD_SALESCHANNEL_ID",
    "OZON_CLIENT_ID", "OZON_API_KEY", "WB_API_KEY", "TELEGRAM_BOT_TOKEN",
    "RECAPTCHA_SITE_KEY", "RECAPTCHA_SECRET_KEY",
]


def create_rows(apps, schema_editor):
    IntegrationKey = apps.get_model("core", "IntegrationKey")
    for key in KEYS:
        IntegrationKey.objects.get_or_create(key=key)


class Migration(migrations.Migration):
    dependencies = [("core", "0004_alter_page_external_url")]
    operations = [
        migrations.CreateModel(
            name="IntegrationKey",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(choices=[(k, k) for k in KEYS], max_length=64, unique=True, verbose_name="Интеграция")),
                ("encrypted_value", models.TextField(blank=True, editable=False, verbose_name="Зашифрованное значение")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
            ],
            options={"verbose_name": "Ключ интеграции", "verbose_name_plural": "Ключи интеграций", "ordering": ("key",)},
        ),
        migrations.RunPython(create_rows, migrations.RunPython.noop),
    ]
