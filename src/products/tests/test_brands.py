from django.test import SimpleTestCase

from products.brands import normalize_brand_title


class BrandNormalizationTests(SimpleTestCase):
    def test_nkbmx_aliases_use_one_catalog_name(self):
        for value in ("NK bmx", "NK BMX", "NKBMX", "nk-bmx", " nk_bmx "):
            with self.subTest(value=value):
                self.assertEqual(normalize_brand_title(value), "NKBMX")

    def test_unrelated_brand_keeps_its_name(self):
        self.assertEqual(normalize_brand_title("  We The People  "), "We The People")
