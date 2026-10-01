import requests
from django.conf import settings
from core.integrations import integration_value


def _get_session():
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {integration_value('MOYSKLAD_TOKEN')}",
        "Accept-Encoding": "gzip",
        "User-Agent": "DjangoSync/1.0",
    })
    return session
