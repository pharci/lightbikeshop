from django import forms

class CheckoutForm(forms.Form):
    receiving_method = forms.ChoiceField(choices=[('pickup', 'Самовывоз'), ('delivery', 'Доставка')], initial='pickup' )
    contact_phone = forms.CharField(max_length=15)
    user_name = forms.CharField(max_length=50)
    pickup_location = forms.ChoiceField(required=False, choices=[('', 'Выберите место самовывоза'), ('alekseevskaya', 'Метро Алексеевская'), ('colntsevo', 'Метро Солнцево')])
    delivery_address = forms.CharField(required=False, max_length=100)
    delivery_method = forms.ChoiceField(required=False, choices=[('', 'Выберите способ доставки'), ('russian_post', 'Почта России'), ('sdek', 'Сдек'), ('boxberry', 'Boxberry')],)
    order_notes = forms.CharField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        receiving_method = cleaned_data.get('receiving_method')
        contact_phone = cleaned_data.get('contact_phone')
        user_name = cleaned_data.get('user_name')
        order_notes = cleaned_data.get('order_notes')

        if receiving_method == 'pickup':
            pickup_location = cleaned_data.get('pickup_location')
            if not contact_phone or not user_name or not pickup_location:
                raise forms.ValidationError('Пожалуйста, заполните все обязательные поля.')

        elif receiving_method == 'delivery':
            delivery_address = cleaned_data.get('delivery_address')
            delivery_method = cleaned_data.get('delivery_method')
            if not contact_phone or not user_name or not delivery_address or not delivery_method:
                raise forms.ValidationError('Пожалуйста, заполните все обязательные поля.')

        return cleaned_data