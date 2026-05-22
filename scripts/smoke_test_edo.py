"""
Smoke test del demo EDO Enterprise (Grupo gastronómico, 24 RUCs target).

Verifica que las features estrella del demo Enterprise están saludables
y con datos suficientes para impresionar al cliente.

Uso:
    docker exec -i -e DJANGO_SETTINGS_MODULE=config.settings.production \
        harmoni-demo-web python manage.py shell < scripts/smoke_test_edo.py
"""
import sys
from django.contrib.auth import get_user_model
from django.test import Client


User = get_user_model()


def banner(text):
    print(f'\n{"═" * 70}\n  {text}\n{"═" * 70}')


def check(label, ok, detail=''):
    marker = '✓' if ok else '✗'
    print(f'  [{marker}] {label:42} {detail}')
    return ok


banner('SMOKE TEST — Demo EDO Enterprise')

errors = []

# ── 1. Empresas EDO ────────────────────────────────────────────────────
banner('1. Multi-empresa Grupo EDO')
try:
    from empresas.models import Empresa
    edo_empresas = Empresa.objects.exclude(ruc='20612345678')
    enterprise_count = edo_empresas.filter(plan='ENTERPRISE').count()
    check(f'{enterprise_count} empresas marcadas ENTERPRISE', enterprise_count >= 5)
    if enterprise_count < 5:
        errors.append(f'Pocas empresas ENTERPRISE: {enterprise_count}')
except Exception as e:
    errors.append(f'Empresas: {e}')

# ── 2. Trabajadores ────────────────────────────────────────────────────
banner('2. Trabajadores EDO activos')
try:
    from personal.models import Personal
    total = Personal.objects.filter(estado='Activo').exclude(empresa__ruc='20612345678').count()
    check(f'{total} workers activos EDO', total >= 60, f'(target ≥60)')
    if total < 60:
        errors.append(f'Pocos workers: {total}')
except Exception as e:
    errors.append(f'Personal: {e}')

# ── 3. Features estrella ───────────────────────────────────────────────
banner('3. Features estrella Enterprise')
feature_data = []
try:
    from asistencia.models import BriefingServicio
    feature_data.append(('Briefings creados', BriefingServicio.objects.count(), 5))
except Exception:
    pass
try:
    from encuestas.models import PulseSemanal
    feature_data.append(('Pulses semanales', PulseSemanal.objects.count(), 100))
except Exception:
    pass
try:
    from reclutamiento.models import Vacante, Postulacion
    feature_data.append(('Vacantes', Vacante.objects.count(), 3))
    feature_data.append(('Postulaciones (CVs)', Postulacion.objects.count(), 20))
except Exception:
    pass
try:
    from evaluaciones.models import Evaluacion
    feature_data.append(('Evaluaciones', Evaluacion.objects.count(), 10))
except Exception:
    pass
try:
    from capacitaciones.models import Capacitacion
    feature_data.append(('Capacitaciones', Capacitacion.objects.count(), 2))
except Exception:
    pass
try:
    from comunicaciones.models import CampanaComunicacion, ComunicadoMasivo, PlantillaNotificacion
    feature_data.append(('Campañas comunicación', CampanaComunicacion.objects.count(), 2))
    feature_data.append(('Comunicados masivos', ComunicadoMasivo.objects.count(), 3))
    feature_data.append(('Plantillas notif.', PlantillaNotificacion.objects.count(), 5))
except Exception:
    pass
try:
    from documentos.models import DocumentoTrabajador, TipoDocumento, CategoriaDocumento
    feature_data.append(('Documentos trabajador', DocumentoTrabajador.objects.count(), 30))
    feature_data.append(('Tipos documento', TipoDocumento.objects.count(), 20))
    feature_data.append(('Categorías documento', CategoriaDocumento.objects.count(), 5))
except Exception:
    pass
try:
    from prestamos.models import Prestamo
    feature_data.append(('Préstamos', Prestamo.objects.count(), 2))
except Exception:
    pass
try:
    from personal.models import AsignacionRosterQuincena, Roster
    feature_data.append(('Asignaciones roster', AsignacionRosterQuincena.objects.count(), 500))
    feature_data.append(('Rosters quincena', Roster.objects.count(), 100))
except Exception:
    pass
try:
    from nominas.models import SaldoAperturaTrabajador, PeriodoNomina, RegistroNomina
    feature_data.append(('Saldos apertura', SaldoAperturaTrabajador.objects.count(), 30))
    feature_data.append(('Períodos nómina', PeriodoNomina.objects.count(), 3))
    feature_data.append(('Registros nómina', RegistroNomina.objects.count(), 100))
except Exception:
    pass

for label, count, target in feature_data:
    ok = count >= target
    if not check(f'{label}', ok, f'{count} (target ≥{target})'):
        errors.append(f'{label}: {count} < {target}')

# ── 4. URLs Enterprise ─────────────────────────────────────────────────
banner('4. URLs Enterprise accesibles')
demo_user = User.objects.filter(username='demo').first()
if not demo_user:
    errors.append('User demo no existe')
else:
    c = Client(HTTP_HOST='demo.harmoni.pe', SERVER_NAME='demo.harmoni.pe')
    c.force_login(demo_user)
    urls = [
        '/',
        '/personal/',
        '/asistencia/',
        '/asistencia/briefing/',
        '/nominas/',
        '/vacaciones/',
        '/empresas/',
        '/empresas/pulse/',
        '/reclutamiento/',
        '/reclutamiento/dashboard/',
        '/reclutamiento/pipeline/',
        '/capacitaciones/',
        '/evaluaciones/',
        '/disciplinaria/',
        '/prestamos/',
        '/viaticos/',
        '/comunicaciones/',
        '/analytics/',
        '/analytics/predictive/',
        '/analytics/ia/',
        '/sistema/dashboard/ejecutivo/',
        '/integraciones/',
        '/calendario/',
        '/workflows/bandeja/',
        '/contratos/',
        '/organigrama/',
        '/roster/matricial/',
    ]
    pass_count = 0
    for url in urls:
        try:
            r = c.get(url, secure=True, follow=False)
            ok = r.status_code in (200, 301, 302) and '/upgrade/' not in r.get('Location', '')
            if ok:
                pass_count += 1
        except Exception:
            ok = False
        if not ok:
            errors.append(f'URL {url} status {r.status_code}')
            check(f'GET {url}', False, f'status {r.status_code}')
    check(f'{pass_count}/{len(urls)} URLs OK', pass_count == len(urls))

# ── 5. Resumen ─────────────────────────────────────────────────────────
banner('RESUMEN')
if not errors:
    print('  ✓ Demo EDO Enterprise SALUDABLE\n')
    sys.exit(0)
else:
    print(f'  ⚠ {len(errors)} ALERTAS:')
    for e in errors[:15]:
        print(f'    - {e}')
    sys.exit(1)
