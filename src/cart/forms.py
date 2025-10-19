from django import forms
from django.core.exceptions import ValidationError
import re

DELIVERY_GROUP_CHOICES = (("pickup", "Самовывоз"), ("pvz", "ПВЗ"))
PHONE_RE = re.compile(r'^(?:\+7|8)?\D?(\d{3})\D?(\d{3})\D?(\d{2})\D?(\d{2})$')

class CheckoutForm(forms.Form):
    payment_type   = forms.CharField(initial="online", widget=forms.HiddenInput)
    city           = forms.CharField()
    delivery_group = forms.ChoiceField(choices=DELIVERY_GROUP_CHOICES, required=False)
    delivery_method= forms.CharField(required=False)
    pvz_provider   = forms.CharField(required=False)
    pvz_code       = forms.CharField(required=False)
    pvz_address    = forms.CharField(required=False)

    last_name      = forms.CharField()
    first_name     = forms.CharField()
    patronymic     = forms.CharField(required=False)
    contact_phone  = forms.CharField()
    order_notes    = forms.CharField(required=False)

    @property
    def user_name(self):
        return self.cleaned_data.get("user_name", "")

    def clean_contact_phone(self):
        raw = (self.cleaned_data.get("contact_phone") or "").strip()
        m = PHONE_RE.match(raw.replace(' ', ''))
        if not m:
            raise ValidationError("Номер в формате +7 (XXX) XXX-XX-XX")
        digits = "7" + "".join(m.groups())  # всегда на 7
        return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"

    def clean(self):
        cd = super().clean()
        s = lambda k: (cd.get(k) or "").strip()

        # ФИО → user_name
        ln, fn, pn = s("last_name"), s("first_name"), s("patronymic")
        cd.update(last_name=ln, first_name=fn, patronymic=pn,
                  user_name=" ".join(p for p in (ln, fn, pn) if p))

        # Город
        city = s("city")
        if not city:
            self.add_error("city", "Укажите город.")
        cd["city"] = city

        # Определение способа доставки
        dg = s("delivery_group") or None
        dm = s("delivery_method") or None
        pvz_provider, pvz_code, pvz_address = s("pvz_provider"), s("pvz_code"), s("pvz_address")

        # Автовывод группы по методу/ПВЗ
        if dm in ("pickup_store", "pickup_pvz"):
            dg = "pickup" if dm == "pickup_store" else "pvz"
        elif pvz_code or pvz_address:
            dg, dm = "pvz", "pickup_pvz"

        if not dg:
            self.add_error("delivery_group", "Выберите способ доставки.")
            cd["payment_type"] = "online"
            return cd

        if dg == "pvz":
            if not (pvz_provider and pvz_code and pvz_address):
                self.add_error("delivery_group", "Выберите пункт выдачи.")
            cd.update(
                delivery_group="pvz",
                delivery_method="pickup_pvz",
                pvz_provider=pvz_provider,
                pvz_code=pvz_code,
                pvz_address=pvz_address,
            )
        elif dg == "pickup":
            # Самовывоз из магазина: ПВЗ-поля сбрасываем
            cd.update(
                delivery_group="pickup",
                delivery_method="pickup_store",
                pvz_provider="",
                pvz_code="",
                pvz_address="",
            )
        else:
            self.add_error("delivery_group", "Неверный способ доставки.")

        cd["payment_type"] = "online"
        return cd