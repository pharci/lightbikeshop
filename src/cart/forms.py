from django import forms

DELIVERY_GROUP_CHOICES = (("pickup", "Самовывоз"), ("pvz", "ПВЗ"))

class CheckoutForm(forms.Form):
    payment_type   = forms.CharField(initial="online", widget=forms.HiddenInput)
    city           = forms.CharField()
    delivery_group = forms.ChoiceField(choices=DELIVERY_GROUP_CHOICES, required=False)
    delivery_method= forms.CharField()
    pvz_provider   = forms.CharField()
    pvz_code       = forms.CharField()
    pvz_address    = forms.CharField()

    last_name      = forms.CharField()
    first_name     = forms.CharField()
    patronymic     = forms.CharField(required=False)
    contact_phone  = forms.CharField()
    email          = forms.EmailField(required=False)
    order_notes    = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("delivery_method", "pvz_provider", "pvz_code", "pvz_address"):
            self.fields[name].required = False

    def clean(self):
        cd = super().clean()

        # нормализация
        def s(key): return (cd.get(key) or "").strip()
        city           = s("city")
        dg             = s("delivery_group") or None
        dm             = s("delivery_method") or None
        pvz_provider   = s("pvz_provider")
        pvz_code       = s("pvz_code")
        pvz_address    = s("pvz_address")

        if not city:
            self.add_error("city", "Укажите город.")
        cd["city"] = city

        # автоопределение метода
        if dm in ("pickup_store", "pickup_pvz"):
            dg = "pickup" if dm == "pickup_store" else "pvz"
        elif pvz_code or pvz_address:
            dg, dm = "pvz", "pickup_pvz"

        if not dg:
            self.add_error("delivery_group", "Выберите способ доставки.")
            cd["payment_type"] = "online"
            return cd

        if dg == "pvz":
            if not pvz_provider or not pvz_code or not pvz_address:
                self.add_error("delivery_group", "Выберите пункт выдачи.")
            cd.update(
                delivery_group="pvz",
                delivery_method="pickup_pvz",
                pvz_provider=pvz_provider,
                pvz_code=pvz_code,
                pvz_address=pvz_address,
            )
        else:
            self.add_error("delivery_group", "Неверный способ доставки.")

        cd["payment_type"] = "online"
        return cd