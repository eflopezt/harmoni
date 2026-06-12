"""
Formularios para el módulo personal.
"""
from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from .models import Area, SubArea, Personal, Roster, Contrato, Adenda


class AreaForm(forms.ModelForm):
    class Meta:
        model = Area
        fields = ['nombre', 'codigo', 'jefe_area', 'responsables', 'descripcion', 'activa']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'responsables': FilteredSelectMultiple(
                verbose_name='Responsables adicionales',
                is_stacked=False
            ),
            'codigo': forms.TextInput(attrs={
                'placeholder': 'Ej: ADM, OPS-01, GG',
                'style': 'text-transform:uppercase',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        personal_qs = Personal.objects.filter(estado='Activo').order_by('apellidos_nombres')
        # Jefe de área — solo 1 persona activa
        self.fields['jefe_area'].queryset = personal_qs
        self.fields['jefe_area'].empty_label = '— Sin jefe asignado —'
        self.fields['jefe_area'].help_text = 'Jefe inmediato del área (aparece en reportes SUNAT)'
        # Responsables — múltiples
        self.fields['responsables'].queryset = personal_qs
        self.fields['responsables'].help_text = 'Personas con acceso de gestión al área (opcional)'

        # No usar Layout de crispy (incompatible Python 3.14 + context.__copy__)
        # El template area_form.html renderiza los campos manualmente


class SubAreaForm(forms.ModelForm):
    class Meta:
        model = SubArea
        fields = ['nombre', 'area', 'descripcion', 'activa']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # No crispy — template renderiza manualmente (Python 3.14 compat)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault('class', 'form-check-input')
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault('class', 'form-select')
            else:
                w.attrs.setdefault('class', 'form-control')


class PersonalForm(forms.ModelForm):
    class Meta:
        model = Personal
        fields = [
            'tipo_doc', 'nro_doc', 'apellidos_nombres', 'codigo_fotocheck',
            'cargo', 'cargo_obj', 'tipo_trab', 'categoria', 'subarea',
            'fecha_alta', 'fecha_cese', 'motivo_cese', 'estado',
            'regimen_pension', 'afp', 'cuspp', 'asignacion_familiar',
            'fecha_nacimiento', 'sexo', 'celular', 'correo_personal', 'correo_corporativo',
            'direccion', 'ubigeo',
            'sueldo_base', 'banco', 'cuenta_ahorros', 'cuenta_cci', 'cuenta_cts',
            'medio_pago_haberes', 'billetera_tipo', 'billetera_celular', 'billetera_acuerdo',
            'cond_trabajo_mensual', 'alimentacion_mensual', 'viaticos_mensual',
            'tiene_eps', 'eps_descuento_mensual',
            'grupo_tareo', 'condicion', 'regimen_laboral', 'regimen_turno',
            'dia_descanso_semanal',
            'codigo_sap', 'codigo_s10', 'partida_control',
            # jornada_horas ocultado — calculado automáticamente por importer
            'dias_libres_corte_2025', 'observaciones',
            # Contrato
            'tipo_contrato', 'fecha_inicio_contrato', 'fecha_fin_contrato',
            'renovacion_automatica', 'observaciones_contrato',
        ]
        widgets = {
            'fecha_alta': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_cese': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_inicio_contrato': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_fin_contrato': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observaciones': forms.Textarea(attrs={'rows': 3}),
            'observaciones_contrato': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Asegurar que las fechas se muestren en el formato correcto
        if self.instance and self.instance.pk:
            if self.instance.fecha_alta:
                self.initial['fecha_alta'] = self.instance.fecha_alta.strftime('%Y-%m-%d')
            if self.instance.fecha_cese:
                self.initial['fecha_cese'] = self.instance.fecha_cese.strftime('%Y-%m-%d')
            if self.instance.fecha_nacimiento:
                self.initial['fecha_nacimiento'] = self.instance.fecha_nacimiento.strftime('%Y-%m-%d')
            if self.instance.fecha_inicio_contrato:
                self.initial['fecha_inicio_contrato'] = self.instance.fecha_inicio_contrato.strftime('%Y-%m-%d')
            if self.instance.fecha_fin_contrato:
                self.initial['fecha_fin_contrato'] = self.instance.fecha_fin_contrato.strftime('%Y-%m-%d')

        # No usar crispy Layout — incompatible con Python 3.14 (context.__copy__).
        # El template personal_form.html renderiza los campos manualmente con Bootstrap.
        # Añadir clases Bootstrap a todos los widgets para renderizado manual.
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault('class', 'form-select')
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault('class', 'form-control')
            else:
                widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        cleaned = super().clean()
        # Ley 32413: pagar por billetera exige acuerdo del trabajador,
        # billetera elegida y celular válido (9 dígitos, empieza en 9).
        if cleaned.get('medio_pago_haberes') == 'BILLETERA':
            if not cleaned.get('billetera_tipo'):
                self.add_error('billetera_tipo', 'Selecciona la billetera (Yape, Plin…).')
            cel = (cleaned.get('billetera_celular') or '').strip()
            if not (len(cel) == 9 and cel.isdigit() and cel.startswith('9')):
                self.add_error('billetera_celular', 'Celular inválido: 9 dígitos empezando en 9.')
            if not cleaned.get('billetera_acuerdo'):
                self.add_error('billetera_acuerdo',
                               'La Ley 32413 exige el acuerdo previo del trabajador '
                               'para pagar por billetera digital.')
        return cleaned


class RosterForm(forms.ModelForm):
    class Meta:
        model = Roster
        fields = ['personal', 'fecha', 'codigo', 'observaciones']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # No crispy — template renderiza manualmente (Python 3.14 compat)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault('class', 'form-check-input')
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault('class', 'form-select')
            else:
                w.attrs.setdefault('class', 'form-control')


class ContratoForm(forms.ModelForm):
    """Formulario para crear/editar contratos laborales."""
    class Meta:
        model = Contrato
        fields = [
            'tipo_contrato', 'numero_contrato', 'fecha_inicio', 'fecha_fin',
            'estado', 'renovacion_automatica', 'sueldo_pactado', 'cargo_contrato',
            'jornada_semanal', 'archivo_pdf', 'observaciones',
        ]
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_fin': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observaciones': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.fecha_inicio:
                self.initial['fecha_inicio'] = self.instance.fecha_inicio.strftime('%Y-%m-%d')
            if self.instance.fecha_fin:
                self.initial['fecha_fin'] = self.instance.fecha_fin.strftime('%Y-%m-%d')
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault('class', 'form-select')
            elif isinstance(widget, forms.FileInput):
                widget.attrs.setdefault('class', 'form-control')
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault('class', 'form-control')
            else:
                widget.attrs.setdefault('class', 'form-control')


class AdendaForm(forms.ModelForm):
    """Formulario para crear adendas a contratos."""
    class Meta:
        model = Adenda
        fields = [
            'fecha', 'tipo_modificacion', 'detalle',
            'valor_anterior', 'valor_nuevo', 'archivo',
        ]
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'detalle': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.fecha:
            self.initial['fecha'] = self.instance.fecha.strftime('%Y-%m-%d')
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault('class', 'form-select')
            elif isinstance(widget, forms.FileInput):
                widget.attrs.setdefault('class', 'form-control')
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault('class', 'form-control')
            else:
                widget.attrs.setdefault('class', 'form-control')


class RenovacionContratoForm(forms.Form):
    """Formulario para renovar un contrato existente."""
    tipo_contrato = forms.ChoiceField(
        choices=Personal.TIPO_CONTRATO_CHOICES,
        label='Modalidad del nuevo contrato',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    fecha_inicio = forms.DateField(
        label='Inicio del nuevo contrato',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    fecha_fin = forms.DateField(
        label='Fin del nuevo contrato',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        help_text='Dejar vacío para contrato indefinido',
    )
    sueldo_pactado = forms.DecimalField(
        label='Sueldo pactado',
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    )
    motivo = forms.CharField(
        label='Motivo de renovación',
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )
    observaciones = forms.CharField(
        label='Observaciones del nuevo contrato',
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
    )


class ImportExcelForm(forms.Form):
    """Formulario para importación de archivos Excel."""
    archivo = forms.FileField(
        label='Archivo Excel',
        help_text='Selecciona un archivo .xlsx o .xls',
        widget=forms.FileInput(attrs={'accept': '.xlsx,.xls'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.attrs = {'enctype': 'multipart/form-data'}
        self.helper.add_input(Submit('submit', 'Importar', css_class='btn btn-primary'))
