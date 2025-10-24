import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lightbikeshop.settings")
app = Celery("lightbikeshop")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.update(
    worker_hijack_root_logger=False,
    worker_redirect_stdouts=False,
)
app.autodiscover_tasks()