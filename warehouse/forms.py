from django import forms

from warehouse.models import PurchaseRequisition, StockIn, Supplier


class RequisitionFromSalesForm(forms.Form):
    date_from = forms.DateField(
        label='С',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    date_to = forms.DateField(
        label='По',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )


class RequisitionNoteForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequisition
        fields = ('note',)
        widgets = {
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class RequisitionHeaderForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequisition
        fields = ('number', 'note')
        widgets = {
            'number': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 32}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean_number(self):
        number = self.cleaned_data['number'].strip()
        if not number:
            raise forms.ValidationError('Укажите номер заявки.')
        qs = PurchaseRequisition.objects.filter(number=number)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Заявка с таким номером уже существует.')
        return number


class RequisitionItemForm(forms.Form):
    product_sku = forms.CharField(
        label='Артикул',
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ABC-123'}),
    )
    quantity = forms.IntegerField(
        label='Количество',
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )


class RequisitionReceiveForm(forms.Form):
    """One row per requisition line with remaining qty."""
    requisition_item_id = forms.IntegerField(widget=forms.HiddenInput)
    receive = forms.BooleanField(required=False, label='Оприходовать')
    quantity = forms.IntegerField(
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': 0}),
    )


class StockInHeaderForm(forms.ModelForm):
    class Meta:
        model = StockIn
        fields = ('supplier', 'date', 'requisition')
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'},
                format='%Y-%m-%dT%H:%M',
            ),
            'requisition': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['requisition'].required = False
        self.fields['requisition'].empty_label = '— без заявки —'
        self.fields['supplier'].queryset = Supplier.objects.order_by('name')
        self.fields['date'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']
        if self.instance and self.instance.pk and self.instance.date:
            from django.utils import timezone
            self.initial.setdefault(
                'date',
                timezone.localtime(self.instance.date).strftime('%Y-%m-%dT%H:%M'),
            )


class StockInItemForm(forms.Form):
    product_sku = forms.CharField(
        label='Артикул',
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ABC-123'}),
    )
    quantity = forms.IntegerField(
        label='Количество',
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )
    purchase_price_rub = forms.DecimalField(
        label='Цена закупки, ₽',
        min_value=0,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    )
