from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from products.models import Brand, Category


class Command(BaseCommand):
    help = "Скачать изображения категорий и брендов с lightbikeshop.ru"

    source_url = "https://lightbikeshop.ru/catalog/"

    def handle(self, *args, **options):
        response = requests.get(
            self.source_url,
            timeout=30,
            headers={"User-Agent": "LightBikeShop catalog image sync"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        session = requests.Session()
        session.headers["User-Agent"] = "LightBikeShop catalog image sync"

        category_count = self._sync_cards(session, soup.select("a.category-card"), Category)
        brand_count = self._sync_cards(session, soup.select("a.brand-card"), Brand)
        self.stdout.write(self.style.SUCCESS(
            f"Изображения обновлены: категории — {category_count}, бренды — {brand_count}"
        ))

    def _sync_cards(self, session, cards, model):
        updated = 0
        for card in cards:
            title = card.get_text(" ", strip=True)
            image = card.select_one("img")
            if not title or not image or not image.get("src"):
                continue
            obj = model.objects.filter(title__iexact=title).first()
            if not obj:
                continue
            image_url = urljoin(self.source_url, image["src"])
            result = session.get(image_url, timeout=30)
            result.raise_for_status()
            filename = Path(unquote(urlparse(image_url).path)).name or f"{obj.pk}.jpg"
            obj.image.save(filename, ContentFile(result.content), save=True)
            updated += 1
            self.stdout.write(f"  {model.__name__}: {title}")
        return updated
