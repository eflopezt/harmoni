"""
Formularios del modulo de Reclutamiento y Seleccion.
"""
from django import forms
from django.contrib.auth.models import User
from django.db.models import Q

from personal.models import Area
from .models import (
    Vacante, EtapaPipeline, Postulacion,
    NotaPostulacion, EntrevistaPrograma,
)


class VacanteForm(forms.ModelForm):
    """Formulario para crear/editar vacantes."""

    class Meta:
        model = Vacante
        fields = [
            'titulo', 'area', 'descripcion', 'requisitos',
            'experiencia_minima', 'educacion_minima', 'tipo_contrato',
            'salario_min', 'salario_max', 'moneda',
            'estado', 'prioridad',
            'fecha_publicacion', 'fecha_limite',
            'responsable', 'publica',
        ]
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'area': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
            'requisitos': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
            'experiencia_minima': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': 0}),
            'educacion_minima': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'tipo_contrato': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'salario_min': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'salario_max': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'moneda': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'estado': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'prioridad': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'fecha_publicacion': forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
            'fecha_limite': forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
            'responsable': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'publica': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        self.fields['area'].queryset = Area.objects.filter(activa=True)
        responsables = User.objects.filter(is_active=True)
        if empresa is not None:
            responsables = responsables.filter(
                Q(personal_data__empresa=empresa) |
                Q(pk=empresa.creado_por_id) |
                Q(is_superuser=True)
            ).distinct()
        self.fields['responsable'].queryset = responsables.order_by(
            'first_name', 'last_name')


class PostulacionAdminForm(forms.ModelForm):
    """Formulario para crear postulaciones desde admin."""

    class Meta:
        model = Postulacion
        fields = [
            'nombre_completo', 'email', 'telefono', 'cv',
            'experiencia_anos', 'educacion', 'salario_pretendido',
            'fuente', 'notas',
        ]
        widgets = {
            'nombre_completo': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'email': forms.EmailInput(attrs={'class': 'form-control form-control-sm'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'cv': forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm'}),
            'experiencia_anos': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': 0}),
            'educacion': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'salario_pretendido': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'fuente': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'notas': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }


class PostulacionPublicaForm(forms.ModelForm):
    """Formulario publico para postularse a una vacante (portal empleo)."""

    class Meta:
        model = Postulacion
        fields = [
            'nombre_completo', 'email', 'telefono', 'cv',
            'experiencia_anos', 'educacion', 'salario_pretendido',
        ]
        widgets = {
            'nombre_completo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre y Apellidos',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'tu@email.com',
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+51 999 999 999',
            }),
            'cv': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx',
            }),
            'experiencia_anos': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'placeholder': '0',
            }),
            'educacion': forms.Select(attrs={'class': 'form-select'}),
            'salario_pretendido': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Opcional',
            }),
        }
        labels = {
            'nombre_completo': 'Nombre Completo',
            'email': 'Correo Electronico',
            'telefono': 'Telefono',
            'cv': 'Curriculum Vitae (PDF)',
            'experiencia_anos': 'Anios de Experiencia',
            'educacion': 'Nivel Educativo',
            'salario_pretendido': 'Expectativa Salarial (S/)',
        }


class EtapaPipelineForm(forms.ModelForm):
    """Formulario para crear/editar etapas del pipeline."""

    class Meta:
        model = EtapaPipeline
        fields = ['nombre', 'codigo', 'orden', 'color', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': 0}),
            'color': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'type': 'color'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class NotaPostulacionForm(forms.ModelForm):
    """Formulario para agregar notas a una postulacion."""

    class Meta:
        model = NotaPostulacion
        fields = ['texto', 'tipo']
        widgets = {
            'texto': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3, 'placeholder': 'Escribe una nota...'}),
            'tipo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        }


class EntrevistaProgramaForm(forms.ModelForm):
    """Formulario para programar entrevistas."""

    class Meta:
        model = EntrevistaPrograma
        fields = [
            'fecha_hora', 'duracion_minutos', 'entrevistador',
            'tipo', 'modalidad', 'ubicacion', 'enlace_virtual', 'notas_pre',
        ]
        widgets = {
            'fecha_hora': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'duracion_minutos': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': 15}),
            'entrevistador': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'tipo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'modalidad': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'ubicacion': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Sala de reuniones, oficina...'}),
            'enlace_virtual': forms.URLInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'https://meet.google.com/...'}),
            'notas_pre': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2, 'placeholder': 'Puntos a evaluar...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['entrevistador'].queryset = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
