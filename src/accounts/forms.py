from django import forms
from .models import User

class RegistrationForm(forms.Form):
    email = forms.EmailField(required=True, widget=forms.EmailInput())
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already in use.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Passwords do not match.')

        return cleaned_data


class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput())
    password = forms.CharField(max_length=64, widget=forms.PasswordInput())

class VerificationCodeForm(forms.Form):
    code = forms.CharField(label='Verification Code', max_length=6, widget=forms.TextInput(attrs={'autocomplete': 'off'}))

class RecoveryForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput())

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError('Аккаунт с указанной почтой не существует.', code='invalid')
        return email

class RecoveryInputPasswordForm(forms.Form):
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Пароли не совпадают.')

        return cleaned_data