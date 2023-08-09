from django import forms

class CheckoutForm(forms.Form):
    address = forms.CharField(max_length=100, required=False)
    city = forms.CharField(max_length=50, required=False)
    zip_code = forms.CharField(max_length=10, required=False)
    phone_number = forms.CharField(max_length=15)
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50, required=False)
    middle_name = forms.CharField(max_length=50)
    delivery_value = forms.CharField(required=False)

    def clean(self):
        cleaned_data = super().clean()

        # Проверка заполнения каждого поля
        address = cleaned_data.get('address')
        city = cleaned_data.get('city')
        zip_code = cleaned_data.get('zip_code')
        phone_number = cleaned_data.get('phone_number')
        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')
        middle_name = cleaned_data.get('middle_name')
        delivery_value = cleaned_data.get('delivery_value')

        if not phone_number or not first_name or not middle_name:
            raise forms.ValidationError('Пожалуйста, заполните все обязательные поля.')

        return cleaned_data