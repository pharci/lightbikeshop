# products/management/commands/import_moysklad_full.py
import time
import requests
from django.core.management.base import BaseCommand

from products.integrations.ms import import_all_products, import_all_variants


class Command(BaseCommand):
    help = "Полная синхронизация с МойСклад: продукты, модификации, остатки. PK = внешние ID (UUID строки)."

    def add_arguments(self, parser):
        parser.add_argument("--no-stock", action="store_true", help="Не обновлять остатки (только каталог)")

    def handle(self, *args, **opts):
        self.stdout.write(self.style.NOTICE("1) Импорт товаров (product)..."))
        self.stdout.write(self.style.SUCCESS(import_all_products()))

        self.stdout.write(self.style.NOTICE("2) Импорт модификаций (variant)..."))
        self.stdout.write(self.style.SUCCESS(import_all_variants()))

        self.stdout.write(self.style.SUCCESS("Готово."))