import django, os, sys
from django.test import Client
from unittest.mock import patch, Mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','lightbikeshop.settings')
django.setup()
from django.conf import settings as djsettings
# allow test client host
djsettings.ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
client = Client()

with patch('cart.views.cdek.requests.get') as req_get:
    mock_resp = Mock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = [{'code': '520', 'city': 'Одинцovo', 'region': 'MO'}]
    req_get.return_value = mock_resp
    r = client.get('/api/pvz/cities/', secure=True, follow=True)
    print('CITIES ->', r.status_code, dict(r.items()))
    try:
        print(r.json())
    except Exception:
        print('body:', r.content[:200])

with patch('cart.views.cdek.get_pvz_by_city_code') as gp:
    gp.return_value = [{'id': '1', 'name': 'PVZ1', 'address': 'Addr', 'lat': 55.0, 'lon': 37.0, 'provider': 'cdek'}]
    r2 = client.get('/api/pvz/cdek/?city_code=520', secure=True, follow=True)
    print('CDEK  ->', r2.status_code, dict(r2.items()))
    try:
        print(r2.json())
    except Exception:
        print('body:', r2.content[:200])
