"""
Formularios para el módulo personal.
"""
from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils import timezone
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from .models import Area, SubArea, Personal, Roster, Contrato, Adenda
from .services.contrato_rules import contratos_solapados, describir_periodo, fecha_inicio_continuidad


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


# Campos que determinan A DÓNDE se le paga al trabajador. Cambiarlos es la
# acción más atacada en sistemas de nómina (fraude "payroll pirates": tomar
# una cuenta admin y desviar el sueldo). Por eso su edición exige confirmar
# la contraseña del usuario y dispara notificación al trabajador.
CAMPOS_PAGO = (
    'banco', 'cuenta_ahorros', 'cuenta_cci', 'cuenta_cts',
    'medio_pago_haberes', 'billetera_tipo', 'billetera_celular',
)


class PersonalForm(forms.ModelForm):
    password_confirma = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        label='Tu contraseña (solo si cambias datos de pago)',
        help_text='Por seguridad, cambiar banco/cuenta/billetera de un '
                  'trabajador existente requiere confirmar tu contraseña.',
    )

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
    
    def __init__(self, *args, user=None, **kwargs):
        self._user = user
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
        else:
            # Nuevo trabajador: régimen laboral por defecto según el rubro de la
            # instancia (construcción/minería → su régimen; resto → GENERAL).
            try:
                from asistencia.models import ConfiguracionSistema
                from core.rubros import regimen_default
                self.initial.setdefault(
                    'regimen_laboral',
                    regimen_default(ConfiguracionSistema.get().rubro),
                )
            except Exception:
                pass

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

        # ── Validación de formato de cuentas (solo si el valor cambió, para
        #    no bloquear ediciones de otros campos con data legacy imperfecta) ──
        def _cambio(campo):
            if not (self.instance and self.instance.pk):
                return bool(cleaned.get(campo))
            return str(cleaned.get(campo) or '') != str(getattr(self.instance, campo, '') or '')

        cci = (cleaned.get('cuenta_cci') or '').replace(' ', '').replace('-', '')
        if cci and _cambio('cuenta_cci'):
            if not (cci.isdigit() and len(cci) == 20):
                self.add_error('cuenta_cci',
                               'El CCI debe tener exactamente 20 dígitos.')
        for campo in ('cuenta_ahorros', 'cuenta_cts'):
            val = (cleaned.get(campo) or '').replace(' ', '').replace('-', '')
            if val and _cambio(campo) and not val.isdigit():
                self.add_error(campo, 'La cuenta solo debe contener dígitos.')

        # ── Re-autenticación al cambiar datos de pago (anti payroll-pirates) ──
        self.campos_pago_cambiados = []
        if self.instance and self.instance.pk:
            self.campos_pago_cambiados = [c for c in CAMPOS_PAGO if _cambio(c)]
            if self.campos_pago_cambiados:
                pwd = cleaned.get('password_confirma') or ''
                if not self._user or not pwd or not self._user.check_password(pwd):
                    self.add_error(
                        'password_confirma',
                        'Estás cambiando los datos de pago de este trabajador '
                        f'({", ".join(self.campos_pago_cambiados)}). '
                        'Confirma tu contraseña para continuar.'
                    )
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
        self.personal = kwargs.pop('personal', None)
        super().__init__(*args, **kwargs)
        self.personal = self.personal or getattr(self.instance, 'personal', None)
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

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo_contrato')
        fecha_inicio = cleaned.get('fecha_inicio')
        fecha_fin = cleaned.get('fecha_fin')
        estado = cleaned.get('estado')

        if tipo == 'INDEFINIDO':
            cleaned['fecha_fin'] = None
            fecha_fin = None
        elif fecha_inicio and not fecha_fin:
            self.add_error(
                'fecha_fin',
                'Los contratos a plazo necesitan una fecha fin. Para dejarlo sin fin, use contrato indefinido.',
            )

        if fecha_inicio and fecha_fin and fecha_fin < fecha_inicio:
            self.add_error('fecha_fin', 'La fecha fin no puede ser anterior a la fecha de inicio.')
        elif estado == 'VIGENTE' and fecha_fin and fecha_fin < timezone.localdate():
            self.add_error('fecha_fin', 'Un contrato vigente no puede tener vencimiento pasado.')

        if self.personal and fecha_inicio and estado == 'VIGENTE':
            conflicto = contratos_solapados(
                self.personal,
                fecha_inicio,
                fecha_fin,
                excluir_pk=getattr(self.instance, 'pk', None),
            ).first()
            if conflicto:
                self.add_error(
                    'fecha_inicio',
                    (
                        'Este periodo se cruza con otro contrato del trabajador '
                        f'({describir_periodo(conflicto)}). Use Renovar si es continuidad '
                        'o registre una adenda si solo cambia una condición.'
                    ),
                )

        return cleaned


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
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
    )
    fecha_fin = forms.DateField(
        label='Fin del nuevo contrato',
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
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

    def __init__(self, *args, **kwargs):
        self.contrato_original = kwargs.pop('contrato_original', None)
        super().__init__(*args, **kwargs)

        if self.contrato_original and self.contrato_original.fecha_fin:
            inicio = fecha_inicio_continuidad(
                contrato=self.contrato_original,
                personal=self.contrato_original.personal,
            )
            self.fields['fecha_inicio'].help_text = (
                f'Continuidad obligatoria desde el {inicio.strftime("%d/%m/%Y")}.'
            )
            self.fields['fecha_inicio'].widget.attrs['readonly'] = 'readonly'
            self.fields['fecha_inicio'].widget.attrs['data-continuidad'] = 'true'

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo_contrato')
        fecha_inicio = cleaned.get('fecha_inicio')
        fecha_fin = cleaned.get('fecha_fin')

        if not self.contrato_original:
            return cleaned

        if not self.contrato_original.fecha_fin:
            raise forms.ValidationError(
                'Un contrato indefinido no se renueva por fecha. Registre una adenda si cambian sueldo, cargo o condiciones.'
            )

        inicio_esperado = fecha_inicio_continuidad(
            contrato=self.contrato_original,
            personal=self.contrato_original.personal,
        )
        if fecha_inicio and fecha_inicio != inicio_esperado:
            self.add_error(
                'fecha_inicio',
                (
                    f'Para renovar sin romper continuidad, el inicio debe ser '
                    f'{inicio_esperado.strftime("%d/%m/%Y")}.'
                ),
            )

        if tipo == 'INDEFINIDO':
            cleaned['fecha_fin'] = None
            fecha_fin = None
        elif fecha_inicio and not fecha_fin:
            self.add_error('fecha_fin', 'Indique el nuevo vencimiento del contrato.')

        if fecha_inicio and fecha_fin and fecha_fin < fecha_inicio:
            self.add_error('fecha_fin', 'El nuevo vencimiento no puede ser anterior al inicio.')
        elif fecha_fin and fecha_fin < timezone.localdate():
            self.add_error('fecha_fin', 'El nuevo vencimiento debe dejar el contrato vigente.')

        conflicto = None
        if fecha_inicio:
            conflicto = contratos_solapados(
                self.contrato_original.personal,
                fecha_inicio,
                fecha_fin,
                excluir_pk=self.contrato_original.pk,
            ).first()
        if conflicto:
            self.add_error(
                'fecha_inicio',
                (
                    'La renovación se cruza con otro contrato registrado '
                    f'({describir_periodo(conflicto)}). Revise el historial antes de continuar.'
                ),
            )

        return cleaned


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
