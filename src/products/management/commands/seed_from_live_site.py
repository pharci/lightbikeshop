import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from products.models import Brand, Category, Image, Product, Variant


class Command(BaseCommand):
    help = "Загрузить небольшую выборку товаров с lightbikeshop.ru в локальную базу"

    pages = [
        ("https://lightbikeshop.ru/catalog/bmx/rims/", "Обода", "Обод", "rims"),
        ("https://lightbikeshop.ru/catalog/bmx/tiers/", "Покрышки", "Покрышка", "tiers"),
        ("https://lightbikeshop.ru/catalog/bmx/seats/", "Сидения", "Сидение", "seats"),
    ]
    brands = ["Alienation", "NKBMX", "Maxxis", "IRC", "Colony", "Light", "Total"]

    def handle(self, *args, **options):
        parent, _ = Category.objects.get_or_create(title="BMX", defaults={"title_plural": "BMX", "title_singular": "BMX", "slug": "bmx"})
        created = updated = 0
        session = requests.Session()
        session.headers["User-Agent"] = "LightBikeShop local development seed"

        for page_url, plural, singular, category_slug in self.pages:
            category, _ = Category.objects.get_or_create(
                slug=category_slug,
                defaults={"title": plural, "title_plural": plural, "title_singular": singular, "parent": parent},
            )
            html = session.get(page_url, timeout=20).text
            soup = BeautifulSoup(html, "html.parser")
            for card in soup.select(".product-card")[:4]:
                title = card.select_one(".product-card__title").get_text(" ", strip=True)
                remote_path = card.get("data-url", "")
                demo_key = "demo:" + remote_path.rstrip("/").split("/")[-1]
                price_text = card.select_one(".product-card__price").get_text(" ", strip=True)
                price = int(re.sub(r"\D", "", price_text) or 0)
                qty_node = card.select_one(".status__qty")
                inventory = int(re.sub(r"\D", "", qty_node.get_text(" ", strip=True)) or 0) if qty_node else 0
                comparable_title = re.sub(r"[\s_-]+", "", title).lower()
                brand_name = next(
                    (b for b in self.brands if re.sub(r"[\s_-]+", "", b).lower() in comparable_title),
                    "Light",
                )
                brand, _ = Brand.objects.get_or_create(slug=slugify(brand_name), defaults={"title": brand_name, "image": ""})
                base_name = title
                for prefix in (singular, brand_name):
                    base_name = re.sub(rf"^\s*{re.escape(prefix)}\s*", "", base_name, flags=re.I)
                variant = Variant.objects.filter(seller_article=demo_key).select_related("product").first()
                if variant:
                    product = variant.product
                    product.base_name, product.category, product.brand = base_name, category, brand
                    product.description = f"Демонстрационный товар, скопированный из {urljoin(page_url, remote_path)}"
                    product.save()
                    variant.price, variant.inventory, variant.is_active = price, inventory, True
                    variant.save()
                    updated += 1
                else:
                    product = Product.objects.create(base_name=base_name, category=category, brand=brand, description=f"Демонстрационный товар с {urljoin(page_url, remote_path)}")
                    variant = Variant.objects.create(product=product, seller_article=demo_key, price=price, inventory=inventory, is_active=True)
                    created += 1
                image = card.select_one("img.product-card__thumbnail")
                if image and image.get("src") and (not variant.images.exists() or not brand.image):
                    image_url = urljoin(page_url, image["src"])
                    response = session.get(image_url, timeout=20)
                    response.raise_for_status()
                    filename = Path(image_url.split("?", 1)[0]).name or f"{variant.id}.webp"
                    if not variant.images.exists():
                        record = Image(variant=variant, alt=title, sort=0)
                        record.image.save(filename, ContentFile(response.content), save=True)
                    if not brand.image:
                        brand.image.save(f"{brand.slug}-{filename}", ContentFile(response.content), save=True)

        self.stdout.write(self.style.SUCCESS(f"Готово: создано {created}, обновлено {updated}"))
