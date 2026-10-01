from django.test import SimpleTestCase

from products.catalog_enrichment import extract_characteristics, extract_description_characteristics, taobao_item_id


class CatalogEnrichmentTests(SimpleTestCase):
    def test_extracts_characteristics_block_with_units(self):
        self.assertEqual(
            extract_description_characteristics(
                "Описание\n\nХарактеристики:\nМатериал - Титан\nВал, мм - 22\nГарантия: 6 месяцев"
            ),
            {"Материал": "Титан", "Вал, мм": "22", "Гарантия": "6 месяцев"},
        )

    def test_parent_item_id_is_shared_by_skus(self):
        self.assertEqual(taobao_item_id("852710083140:sku:123"), "852710083140")

    def test_extracts_bicycle_characteristics(self):
        values = extract_characteristics(
            "NKBMX титановый руль черный",
            "颜色分类：上管 20.5寸（36孔） 左驱 165mm",
        )
        self.assertEqual(values["Цвет"], "Чёрный")
        self.assertEqual(values["Материал"], "Титановый сплав")
        self.assertEqual(values["Сторона привода"], "Левая")
        self.assertEqual(values["Размер"], '20.5"')
        self.assertEqual(values["Количество отверстий"], "36")
        self.assertEqual(values["Длина"], "165 мм")
