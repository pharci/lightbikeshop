from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("products", "0010_brand_description")]
    operations = [
        migrations.CreateModel(
            name="TaobaoImportItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_key", models.CharField(max_length=255, unique=True, verbose_name="Ключ Taobao")),
                ("store", models.CharField(max_length=100, verbose_name="Магазин")),
                ("external_id", models.CharField(max_length=200, verbose_name="ID / SKU Taobao")),
                ("title_original", models.TextField(verbose_name="Исходное название")), ("title_ru", models.TextField(blank=True, verbose_name="Название на русском")),
                ("description_ru", models.TextField(blank=True, verbose_name="Описание")), ("category_name", models.CharField(blank=True, max_length=100, verbose_name="Категория")),
                ("brand_name", models.CharField(blank=True, max_length=100, verbose_name="Бренд")), ("variant_name", models.TextField(blank=True, verbose_name="Вариант")),
                ("price_cny", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name="Цена CNY")), ("price_rub", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name="Цена ₽")),
                ("available", models.BooleanField(default=True, verbose_name="В наличии")), ("image_url", models.URLField(blank=True, max_length=1000, verbose_name="Фото")),
                ("product_url", models.URLField(blank=True, max_length=1000, verbose_name="Карточка Taobao")), ("status", models.CharField(choices=[("pending", "Ожидает проверки"), ("imported", "Импортирован"), ("rejected", "Отклонён")], db_index=True, default="pending", max_length=16)),
                ("raw", models.JSONField(blank=True, default=dict)), ("received_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="taobao_imports", to="products.product")),
                ("variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="taobao_imports", to="products.variant")),
            ], options={"verbose_name": "Черновик Taobao", "verbose_name_plural": "Черновики Taobao", "ordering": ("-updated_at",)},
        ),
        migrations.AddIndex(model_name="taobaoimportitem", index=models.Index(fields=["status", "store", "updated_at"], name="products_ta_status_e55470_idx")),
    ]
