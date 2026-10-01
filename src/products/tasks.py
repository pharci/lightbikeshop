import logging

import requests
from celery import shared_task
from products.management.commands.sync_taobao_parser import Command as SyncTaobaoParserCommand
from products.integrations.sync_inventory import sync_inventory

logger = logging.getLogger(__name__)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def update_inventory_minutely(self):
    return sync_inventory()

@shared_task
def sync_taobao_parser_minutely():
    try:
        return SyncTaobaoParserCommand().sync()
    except requests.RequestException as exc:
        logger.warning("Skipping Taobao sync because parser is unavailable: %s", exc)
        return 0