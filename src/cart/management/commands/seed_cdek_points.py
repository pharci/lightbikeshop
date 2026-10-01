import json
import re

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from cart.models import PickupPoint


class Command(BaseCommand):
    help = "Временно загрузить московские ПВЗ СДЭК с публичной карты"
    url = "https://cdek-ip.ru/gorod/moskva/"

    def handle(self, *args, **options):
        response = requests.get(self.url, headers={"User-Agent": "Mozilla/5.0"}, timeout=40)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        match = re.search(r"\bpoints\s*=\s*(\[\[.*?\]\])\s*,\s*geoObjects", response.text, re.S)
        if not match:
            raise RuntimeError("На странице СДЭК не найден список координат")
        points = json.loads(match.group(1))
        cards = soup.select(".fdh")
        if len(points) != len(cards):
            raise RuntimeError(f"Количество карточек и координат различается: {len(cards)} / {len(points)}")

        created = updated = 0
        for index, (card, coords) in enumerate(zip(cards, points)):
            def value(prefix):
                node = card.select_one(f'[class^="{prefix}_"]')
                return node.get_text(" ", strip=True) if node else ""
            original_code = value("kod") or str(index + 1)
            code = f"TEMP-CDEK-{original_code}"[:50]
            _, was_created = PickupPoint.objects.update_or_create(
                code=code,
                defaults={
                    "slug": f"temp-cdek-{original_code.lower()}"[:50],
                    "title": value("title") or f"СДЭК {original_code}",
                    "city": "Москва",
                    "address": value("adress"),
                    "metro": value("metro"),
                    "lat": float(coords[0]), "lon": float(coords[1]),
                    "schedule": value("raspisanie")[:180],
                    "is_active": True, "is_main": False, "sort": 500,
                },
            )
            created += int(was_created)
            updated += int(not was_created)
        self.stdout.write(self.style.SUCCESS(f"ПВЗ СДЭК: создано {created}, обновлено {updated}"))
