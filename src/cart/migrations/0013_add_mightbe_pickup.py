from django.db import migrations


def add_mightbe(apps, schema_editor):
    PickupPoint = apps.get_model("cart", "PickupPoint")
    PickupPoint.objects.update_or_create(
        code="MIGHTBE-SOKOLNIKI",
        defaults={
            "slug": "mightbe-sokolniki",
            "title": "Шоурум MightBe",
            "city": "Москва",
            "address": "Москва, Сокольническая площадь, 4к1-2",
            "metro": "Сокольники",
            "lat": 55.7891,
            "lon": 37.6797,
            "schedule": "Ежедневно 11:00–20:00",
            "is_active": True,
            "is_main": True,
            "sort": 1,
        },
    )


def remove_mightbe(apps, schema_editor):
    apps.get_model("cart", "PickupPoint").objects.filter(code="MIGHTBE-SOKOLNIKI").delete()


class Migration(migrations.Migration):
    dependencies = [("cart", "0012_preorder_procurement")]
    operations = [migrations.RunPython(add_mightbe, remove_mightbe)]
