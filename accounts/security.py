import datetime
from functools import wraps
from django.shortcuts import render, redirect
import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
import os
from cryptography.hazmat.primitives import serialization

private_key_path = 'private.pem'


def generate_private_key():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    return private_key

def save_private_key(private_key, private_key_path):
    with open(private_key_path, 'wb') as f:
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        f.write(private_key_bytes)

def load_private_key(private_key_path):
    with open(private_key_path, 'rb') as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )
    return private_key

# Check if the private key file exists
if not os.path.isfile(private_key_path):
    private_key = generate_private_key()
    save_private_key(private_key, private_key_path)

private_key = load_private_key(private_key_path)


# Подпись токена
def sign_token(payload, private_key):
    encoded_token = jwt.encode(payload, private_key, algorithm='RS256')
    return encoded_token

# Проверка токена
def verify_token(token, public_key):
    try:
        decoded_token = jwt.decode(token, public_key, algorithms=['RS256'])
        return True
    except (jwt.exceptions.InvalidTokenError, jwt.exceptions.DecodeError):
        return False

def check_token(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        token = request.session.get('token')
        if not token:
            return redirect('accounts:login')
        
        public_key = load_private_key(private_key_path).public_key()

        is_valid = verify_token(token, public_key)
        if not is_valid:
            return redirect('accounts:login')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper

def generate_token(request, action):
    private_key = load_private_key(private_key_path)

    # Генерация токена
    payload = {
        'action': action,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
    }
    encoded_token = sign_token(payload, private_key)

    # Сохранение токена в сеансе пользователя
    request.session['token'] = encoded_token