import json
from django.test import TestCase, override_settings
from django.urls import reverse
from products.models import TaobaoImportItem


@override_settings(TAOBAO_IMPORT_TOKEN="test-secret")
class TaobaoImportAPITests(TestCase):
    def test_requires_token(self):
        response = self.client.post(reverse("products:taobao-import"), data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_updates_without_duplicates(self):
        item = {"store": "EVOBMX", "external_id": "123:sku:7", "title": "测试 BMX", "title_ru": "BMX седло", "price_rub": 1990, "available": True}
        auth = {"HTTP_AUTHORIZATION": "Bearer test-secret"}
        first = self.client.post(reverse("products:taobao-import"), data=json.dumps({"items": [item]}), content_type="application/json", **auth)
        self.assertEqual(first.status_code, 200)
        item["price_rub"] = 2090
        second = self.client.post(reverse("products:taobao-import"), data=json.dumps({"items": [item]}), content_type="application/json", **auth)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(TaobaoImportItem.objects.count(), 1)
        self.assertEqual(TaobaoImportItem.objects.get().price_rub, 2090)
