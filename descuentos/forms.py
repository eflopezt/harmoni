from django import forms

from .models import DescuentoPlanilla


class DescuentoPlanillaForm(forms.ModelForm):
    class Meta:
        model = DescuentoPlanilla
        fields = [
            'personal', 'causal', 'detalle',
            'monto_total', 'num_cuotas', 'cuota_mensual',
            'fecha_inicio_descuento', 'requiere_consentimiento',
            'consentimiento_firmado', 'documento_soporte', 'observaciones',
        ]
        widgets = {
            'detalle': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'personal': forms.Select(attrs={'class': 'form-select'}),
            'causal': forms.Select(attrs={'class': 'form-select'}),
            'monto_total': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0.01',
            }),
            'num_cuotas': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '1', 'max': '36',
            }),
            'cuota_mensual': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01',
                'placeholder': 'Auto (monto / cuotas)',
            }),
            'fecha_inicio_descuento': forms.DateInput(attrs={
                'class': 'form-control', 'type': 'date',
            }),
        }

    def clean(self):
        cd = super().clean()
        monto = cd.get('monto_total')
        n = cd.get('num_cuotas')
        cuota = cd.get('cuota_mensual')
        if monto and n and cuota:
            total_calc = cuota * n
            # Permite 1 centavo de tolerancia por redondeo
            if abs(total_calc - monto) > 1:
                raise forms.ValidationError(
                    f'Cuota × N° cuotas ({total_calc}) no cuadra con monto total ({monto}).'
                )
        return cd
