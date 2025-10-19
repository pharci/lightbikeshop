from django.shortcuts import redirect
from django.urls import reverse

class LoginValidationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == reverse('accounts:login'):
            if request.user.is_authenticated:
                return redirect('accounts:profile')
                
        response = self.get_response(request)
        return response