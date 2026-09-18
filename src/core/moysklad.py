import requests
from django.conf import settings


def _get_session():
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {settings.MOYSKLAD_TOKEN}",
        "Accept-Encoding": "gzip",
        "User-Agent": "DjangoSync/1.0",
    })
    return session
