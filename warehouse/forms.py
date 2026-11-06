from django import forms

from warehouse.models import PurchaseRequisition, StockIn, StockOut, Supplier


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


class ExcelFileForm(forms.Form):
    file = forms.FileField(
        label='Файл Excel (.xlsx)',
        widget=forms.ClearableFileInput(attrs={'accept': '.xlsx', 'class': 'form-control'}),
    )

    def clean_file(self):
        uploaded = self.cleaned_data['file']
        if not uploaded.name.lower().endswith('.xlsx'):
            raise forms.ValidationError('Допустим только формат .xlsx')
        if uploaded.size > 10 * 1024 * 1024:
            raise forms.ValidationError('Файл слишком большой (макс. 10 МБ).')
        return uploaded


class StockInImportForm(ExcelFileForm):
    supplier = forms.ModelChoiceField(
        label='Поставщик',
        queryset=Supplier.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    requisition = forms.ModelChoiceField(
        label='Заявка',
        queryset=PurchaseRequisition.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].queryset = Supplier.objects.order_by('name')
        self.fields['requisition'].queryset = PurchaseRequisition.objects.order_by('-created_at')
        self.fields['requisition'].empty_label = '— без заявки —'
        self.order_fields(['supplier', 'requisition', 'file'])


class StockOutHeaderForm(forms.ModelForm):
    class Meta:
        model = StockOut
        fields = ('date', 'note')
        widgets = {
            'date': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'},
                format='%Y-%m-%dT%H:%M',
            ),
            'note': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Продажа вне сайта, брак…'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']
        self.fields['note'].required = False
        if self.instance and self.instance.pk and self.instance.date:
            from django.utils import timezone
            self.initial.setdefault(
                'date',
                timezone.localtime(self.instance.date).strftime('%Y-%m-%dT%H:%M'),
            )


class StockOutItemForm(forms.Form):
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
    price_rub = forms.DecimalField(
        label='Цена, ₽',
        min_value=0,
        required=False,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    )
