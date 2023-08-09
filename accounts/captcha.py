import requests
from django.conf import settings

def verify_recaptcha(response):
    secret_key = settings.RECAPTCHA_SECRET_KEY
    url = 'https://www.google.com/recaptcha/api/siteverify'
    payload = {
        'secret': secret_key,
        'response': response
    }
    response = requests.post(url, data=payload)

    data = response.json()

    if data['success']:
        return True
    else:
        return False