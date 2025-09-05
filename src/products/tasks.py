from celery import shared_task
from products.MS.sync_inventory import sync_inventory

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def update_inventory_minutely(self):
    return sync_inventory()