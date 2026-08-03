from django import forms

from orders.models import Order


class CheckoutForm(forms.Form):
    customer_name = forms.CharField(
        label='Имя',
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    phone = forms.CharField(
        label='Телефон',
        max_length=64,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    messenger = forms.ChoiceField(
        label='Мессенджер',
        choices=Order.Messenger.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    messenger_contact = forms.CharField(
        label='Ник / номер в мессенджере',
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    delivery_method = forms.ChoiceField(
        label='Способ получения',
        choices=Order.DeliveryMethod.choices,
        widget=forms.RadioSelect,
    )
    delivery_address = forms.CharField(
        label='Адрес доставки',
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )
    comment = forms.CharField(
        label='Комментарий',
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('delivery_method') == Order.DeliveryMethod.DELIVERY:
            if not cleaned.get('delivery_address', '').strip():
                self.add_error('delivery_address', 'Укажите адрес доставки.')
        return cleaned


class AddToCartForm(forms.Form):
    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )
