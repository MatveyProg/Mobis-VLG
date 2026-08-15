from django import forms


class ProductImportForm(forms.Form):
    file = forms.FileField(
        label='Файл Excel (.xlsx)',
        help_text='Первая строка — заголовки столбцов. Данные со второй строки.',
        widget=forms.ClearableFileInput(attrs={'accept': '.xlsx'}),
    )

    def clean_file(self):
        uploaded = self.cleaned_data['file']
        if not uploaded.name.lower().endswith('.xlsx'):
            raise forms.ValidationError('Допустим только формат .xlsx')
        if uploaded.size > 10 * 1024 * 1024:
            raise forms.ValidationError('Файл слишком большой (макс. 10 МБ).')
        return uploaded
