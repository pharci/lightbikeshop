from django.test import TestCase, override_settings

from products.models import Category


@override_settings(
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=["testserver"],
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "missing-category-test",
        }
    },
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class MissingCategoryTests(TestCase):
    def test_missing_category_returns_404(self):
        response = self.client.get("/catalog/asdasdasdasd/")

        self.assertEqual(response.status_code, 404)

    def test_missing_subcategory_returns_404(self):
        Category.objects.create(title="BMX", title_plural="BMX", slug="bmx")

        response = self.client.get("/catalog/bmx/asdasdasd/")

        self.assertEqual(response.status_code, 404)