from django import forms

DELIVERY_GROUP_CHOICES = (("pickup", "Самовывоз"), ("pvz", "ПВЗ"))

class CheckoutForm(forms.Form):
    # 1) оплата — фиксируем онлайн, поле не показываем (но придёт как hidden)
    payment_type = forms.CharField(initial="online", widget=forms.HiddenInput)

    # 2) адрес и способ
    city = forms.CharField()
    delivery_group = forms.ChoiceField(choices=DELIVERY_GROUP_CHOICES, required=False)
    delivery_method = forms.CharField(required=False)   # 'pickup_store' | 'pickup_pvz'
    pickup_location = forms.CharField(required=False)   # строка "Название, адрес"
    pvz_code = forms.CharField(required=False)
    pvz_address = forms.CharField(required=False)

    # 3) получатель
    last_name = forms.CharField()
    first_name = forms.CharField()
    patronymic = forms.CharField(required=False)
    contact_phone = forms.CharField()
    email = forms.EmailField(required=False)
    order_notes = forms.CharField(required=False)

    @property
    def user_name(self):
        if not self.is_valid():
            return ""
        cd = self.cleaned_data
        return " ".join(filter(None, [cd.get("last_name"), cd.get("first_name"), cd.get("patronymic")])).strip()

    def clean(self):
        cd = super().clean()

        # город
        city = (cd.get("city") or "").strip()

        dg = (cd.get("delivery_group") or "").strip() or None
        dm = (cd.get("delivery_method") or "").strip() or None
        pickup_location = (cd.get("pickup_location") or "").strip()
        pvz_code = (cd.get("pvz_code") or "").strip()
        pvz_address = (cd.get("pvz_address") or "").strip()

        # автоопределение метода
        if dm in ("pickup_store", "pickup_pvz"):
            dg = "pickup" if dm == "pickup_store" else "pvz"
        elif pvz_code or pvz_address:
            dg, dm = "pvz", "pickup_pvz"
        elif pickup_location:
            dg, dm = "pickup", "pickup_store"

        if not dg:
            self.add_error("delivery_group", "Выберите способ доставки.")
            return cd

        if dg == "pickup":
            if not pickup_location:
                self.add_error("pickup_location", "Выберите пункт самовывоза.")
            cd["delivery_method"] = "pickup_store"
            cd["pvz_code"] = ""
            cd["pvz_address"] = pickup_location

        elif dg == "pvz":
            if not (pvz_code or pvz_address):
                self.add_error("pvz_code", "Выберите ПВЗ на карте.")
                self.add_error("pvz_address", "Адрес ПВЗ обязателен.")
            cd["delivery_method"] = "pickup_pvz"
            cd["pvz_code"] = pvz_code
            cd["pvz_address"] = pvz_address

        else:
            self.add_error("delivery_group", "Неверный способ доставки.")

        # ЖЁСТКО фиксируем онлайн-оплату
        cd["payment_type"] = "online"

        return cd
