"""
Alta rápida de personal eventual / por evento — caso de uso gastronomía.

Permite registrar en 30 segundos a un trabajador que viene solo para un evento
puntual (catering, fiesta, banquete) sin pasar por el wizard completo de Personal.

Crea:
  - Personal (tipo_contrato=DISCONTINUO, condicion=LOCAL, grupo_tareo=STAFF)
  - Contrato (modal "Intermitente/Discontinuo" — D.S. 003-97-TR Art. 65)
  - Fecha alta = hoy, fecha cese = fecha del evento + 1 día (auto-cese)

Después de la fecha del evento, un cron diario marca como cesado a estos
trabajadores eventuales (--auto-cese).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.shortcuts import redirect, render

from personal.models import Personal, Contrato, SubArea


# RBAC (WS1): superuser o staff con mod_personal en su perfil.
from core.permisos import requiere_modulo
solo_admin = requiere_modulo('personal')
@login_required
@solo_admin
def eventual_nuevo(request):
    """Form minimalista para alta de personal eventual."""

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Obligatorios
                nro_doc = request.POST.get('nro_doc', '').strip()
                apellidos_nombres = request.POST.get('apellidos_nombres', '').strip().upper()
                fecha_evento_str = request.POST.get('fecha_evento', '').strip()
                pago_total_str = request.POST.get('pago_total', '').strip()
                cargo = request.POST.get('cargo', 'Personal de eventos').strip()
                subarea_id = request.POST.get('subarea_id', '')

                # Validaciones
                if not nro_doc:
                    raise ValueError('DNI obligatorio')
                if not apellidos_nombres:
                    raise ValueError('Apellidos y Nombres obligatorios')
                if not fecha_evento_str:
                    raise ValueError('Fecha del evento obligatoria')
                if not pago_total_str:
                    raise ValueError('Pago total del evento obligatorio')

                from datetime import datetime
                fecha_evento = datetime.strptime(fecha_evento_str, '%Y-%m-%d').date()
                pago_total = Decimal(pago_total_str)

                # ¿Ya existe el trabajador?
                p = Personal.objects.filter(nro_doc=nro_doc).first()
                if p:
                    # Re-activar: si estaba cesado, lo reactivamos para este evento
                    if p.estado == 'Cesado':
                        p.estado = 'Activo'
                        p.fecha_cese = None
                        p.motivo_cese = ''
                        p.tipo_contrato = 'DISCONTINUO'
                    p.cargo = cargo
                    if subarea_id:
                        try:
                            p.subarea_id = int(subarea_id)
                        except ValueError:
                            pass
                    p.save()
                    creado = False
                else:
                    # Crear con datos mínimos viables
                    sa = None
                    if subarea_id:
                        sa = SubArea.objects.filter(pk=subarea_id).first()

                    # Detectar empresa actual del request si está
                    empresa = getattr(request, 'empresa_actual', None)
                    if not empresa:
                        # Fallback: empresa principal
                        from empresas.models import Empresa
                        empresa = Empresa.objects.filter(es_principal=True, activa=True).first()

                    p = Personal.objects.create(
                        nro_doc=nro_doc,
                        tipo_doc='DNI',
                        apellidos_nombres=apellidos_nombres,
                        sexo=request.POST.get('sexo', 'M'),
                        celular=request.POST.get('celular', '').strip(),
                        cargo=cargo,
                        empresa=empresa,
                        subarea=sa,
                        grupo_tareo='STAFF',
                        condicion='LOCAL',
                        categoria='EMPLEADO',
                        tipo_contrato='DISCONTINUO',
                        regimen_laboral='GENERAL',
                        regimen_pension=request.POST.get('regimen_pension', 'ONP'),
                        sueldo_base=pago_total,  # como referencia
                        fecha_alta=date.today(),
                        # Auto-cese al día siguiente del evento
                        fecha_fin_contrato=fecha_evento + timedelta(days=1),
                        estado='Activo',
                        observaciones=f'Personal de evento {fecha_evento.isoformat()}. '
                                      f'Pago acordado: S/ {pago_total} por el día.',
                    )
                    creado = True

                # Crear Contrato discontinuo asociado
                Contrato.objects.create(
                    personal=p,
                    tipo_contrato='DISCONTINUO',
                    numero_contrato=f'EVT-{date.today().isoformat()}-{nro_doc[-4:]}',
                    fecha_inicio=date.today(),
                    fecha_fin=fecha_evento + timedelta(days=1),
                    sueldo_pactado=pago_total,
                    renovacion_automatica=False,
                    estado='VIGENTE',
                )

                messages.success(
                    request,
                    f'{"Creado" if creado else "Actualizado"} personal eventual: '
                    f'{apellidos_nombres} ({nro_doc}). '
                    f'Evento: {fecha_evento_str} · Pago: S/ {pago_total}. '
                    f'Se programó auto-cese para el {(fecha_evento + timedelta(days=1)).isoformat()}.'
                )
                return redirect('personal_detail', pk=p.pk)

        except Exception as e:
            messages.error(request, f'Error al registrar: {e}')

    # GET: render form
    subareas = SubArea.objects.filter(activa=True).select_related('area').order_by('area__nombre', 'nombre')
    return render(request, 'personal/eventual_nuevo.html', {
        'titulo': 'Alta rápida — Personal de eventos',
        'subareas': subareas,
        'hoy': date.today().isoformat(),
        'manana': (date.today() + timedelta(days=1)).isoformat(),
    })
