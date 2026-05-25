"""
Performance audit: N+1 queries in the 5 most-used ERP views.

Strategy: usar `connection.queries` (DEBUG=True) o `assertNumQueries(MAX)`
para verificar que el número de queries NO crece con el número de filas
(N+1 syndrome). Si una view itera 10 registros con FK sin select_related,
verás ~10+ queries extra que con select_related serían 0.

Views auditadas:
  1. personal/personal_list  → ya tiene select_related('subarea','subarea__area','empresa')
  2. asistencia/dashboard    → usa solo aggregations, no itera relaciones
  3. nominas/nominas_panel   → select_related en periodos y top_sueldos
  4. vacaciones/vacaciones_panel → select_related en solicitudes y vac_mes
  5. reclutamiento/pipeline_panel → select_related en postulaciones

Los thresholds elegidos se basan en la baseline medida tras los fixes.
Si alguien introduce un N+1 nuevo, el test fallará al crecer los queries
linealmente con el dataset de prueba (10 filas).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='perf_admin', password='x', email='perf@ex.com',
    )


@pytest.fixture
def admin_client(admin_user):
    c = Client()
    c.force_login(admin_user)
    return c


@pytest.fixture
def area_y_subareas(db):
    """Crea 1 Area + 3 SubAreas para distribuir personal."""
    from personal.models import Area, SubArea
    area = Area.objects.create(nombre='Operaciones Perf')
    subs = [
        SubArea.objects.create(nombre=f'SubArea {i}', area=area)
        for i in range(3)
    ]
    return area, subs


@pytest.fixture
def empresa(db):
    """Empresa para multi-tenant."""
    from empresas.models import Empresa
    return Empresa.objects.create(
        subdominio='perftest',
        razon_social='Perf Test SAC',
        ruc='20111222333',
        plan='PROFESIONAL',
        activa=True,
    )


@pytest.fixture
def personal_10(area_y_subareas, empresa):
    """10 personas distribuidas en 3 subáreas distintas, todas Activas."""
    _, subs = area_y_subareas
    from personal.models import Personal
    personas = []
    for i in range(10):
        p = Personal.objects.create(
            nro_doc=f'5000000{i:02d}',
            apellidos_nombres=f'TEST{i:02d}, PERFORMANCE',
            cargo='Operario',
            tipo_trab='Empleado',
            estado='Activo',
            subarea=subs[i % 3],
            empresa=empresa,
            fecha_alta=date(2024, 1, 1),
            sueldo_base=Decimal('2500'),
            grupo_tareo='STAFF' if i % 2 else 'RCO',
            regimen_pension='ONP',
        )
        personas.append(p)
    return personas


# ═══════════════════════════════════════════════════════════════════════
# 1. personal/personal_list
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_personal_list_no_n_plus_1(admin_client, personal_10):
    """personal_list NO debe escalar con N personas.

    El template accede a `p.subarea.nombre` para cada fila. Sin
    select_related, cada acceso dispara una query → 10 queries extra.
    Con select_related (estado actual), 0 queries extra.

    Threshold: <= 30 queries totales para 10 filas. El presupuesto
    cubre auth, middleware tenant, sidebar context, list query, counts
    para badges, paginator, subareas dropdown, empresas dropdown.
    """
    url = reverse('personal_list')
    # warm up para no contar primera-ejecución cold cache de middleware
    admin_client.get(url)
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as ctx:
        r = admin_client.get(url)
    assert r.status_code == 200, f'Esperaba 200, vino {r.status_code}'
    nq = len(ctx.captured_queries)
    # Baseline medida: 10 queries (session, user, empresa sidebar, personal list,
    # 3 count badges, paginator count, subareas dropdown, empresas dropdown).
    # Threshold 15 deja margen para 1-2 queries nuevas razonables sin enmascarar N+1.
    assert nq <= 15, (
        f'personal_list hizo {nq} queries con 10 filas — sospecha N+1. '
        f'Baseline: 10. Threshold: 15. Para debug, imprimir ctx.captured_queries.'
    )


@pytest.mark.django_db
def test_personal_list_queries_stable_with_more_rows(admin_client, area_y_subareas, empresa):
    """El número de queries debe ser ~constante al pasar de 10 → 30 personas."""
    from personal.models import Personal
    _, subs = area_y_subareas
    for i in range(30):
        Personal.objects.create(
            nro_doc=f'6000000{i:02d}',
            apellidos_nombres=f'BULK{i:02d}',
            cargo='Op',
            tipo_trab='Empleado',
            estado='Activo',
            subarea=subs[i % 3],
            empresa=empresa,
            sueldo_base=Decimal('2000'),
            grupo_tareo='STAFF',
        )
    url = reverse('personal_list')
    admin_client.get(url)
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as ctx:
        admin_client.get(url)
    # Con 30 filas debe seguir bajo el mismo threshold (no crece con N).
    # Si se viera 40+ aquí mientras 10 con 10 filas, sería N+1 confirmado.
    assert len(ctx.captured_queries) <= 15, (
        'queries crecen con el número de filas — N+1 detectado'
    )


# ═══════════════════════════════════════════════════════════════════════
# 2. asistencia/dashboard (tareo_dashboard)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_asistencia_dashboard_no_n_plus_1(admin_client, personal_10):
    """tareo_dashboard usa solo aggregations — debe ser O(1) en queries.

    Crea unos pocos RegistroTareo para que no quede vacío. El view itera
    solo `he_elevadas` (dicts de .values()), y `ultimas_imports` que
    solo lee fields directos.
    """
    from asistencia.models import RegistroTareo, TareoImportacion
    hoy = date.today()
    imp = TareoImportacion.objects.create(
        tipo='RELOJ',
        estado='COMPLETADO',
        archivo_nombre='perf_test.xlsx',
        periodo_inicio=date(hoy.year, hoy.month, 1),
        periodo_fin=date(hoy.year, hoy.month, 28),
    )
    for i, p in enumerate(personal_10[:5]):
        RegistroTareo.objects.create(
            importacion=imp,
            personal=p,
            dni=p.nro_doc,
            grupo='STAFF',
            fecha=date(hoy.year, hoy.month, 1) + timedelta(days=i),
            codigo_dia='NOR',
            horas_normales=Decimal('8'),
        )

    url = reverse('asistencia_dashboard')
    admin_client.get(url)  # warm-up
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as ctx:
        r = admin_client.get(url)
    assert r.status_code == 200
    nq = len(ctx.captured_queries)
    # Baseline: 22 queries (muchas aggregaciones por mes, banco horas, alertas,
    # contratos por vencer, sin_registro check, etc.). NO debe escalar con N
    # porque todo es .count()/.aggregate(), sin loop sobre relaciones.
    assert nq <= 30, (
        f'asistencia_dashboard hizo {nq} queries — esperado <= 30 (solo aggs). '
        f'Baseline: 22.'
    )


# ═══════════════════════════════════════════════════════════════════════
# 3. nominas/nominas_panel
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_nominas_panel_no_n_plus_1(admin_client, personal_10):
    """nominas_panel itera periodos (sin FK chain) y top_sueldos (con select_related personal)."""
    from nominas.models import PeriodoNomina, RegistroNomina
    # Crear 3 períodos
    periodos_creados = []
    for mes in [3, 4, 5]:
        p = PeriodoNomina.objects.create(
            tipo='REGULAR', anio=2026, mes=mes,
            estado='APROBADO',
            fecha_inicio=date(2026, mes, 1),
            fecha_fin=date(2026, mes, 28),
            total_neto=Decimal('50000'),
            total_trabajadores=10,
        )
        periodos_creados.append(p)

    # Registros para que top_sueldos no esté vacío (último período)
    ultimo = periodos_creados[-1]
    for persona in personal_10[:5]:
        RegistroNomina.objects.create(
            periodo=ultimo,
            personal=persona,
            sueldo_base=Decimal('2500'),
            total_ingresos=Decimal('2500'),
            total_descuentos=Decimal('300'),
            neto_a_pagar=Decimal('2200'),
        )

    url = reverse('nominas_panel')
    admin_client.get(url)  # warm-up
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as ctx:
        r = admin_client.get(url)
    assert r.status_code == 200
    nq = len(ctx.captured_queries)
    # Baseline: 12 queries (sidebar + periodos + ultimo + ultimos_3 + ultimos_6 +
    # distribución conceptos + top_sueldos + anios_disp + calendario procesos).
    # top_sueldos itera 5 personas pero usa select_related('personal') → sin N+1.
    assert nq <= 20, (
        f'nominas_panel hizo {nq} queries — esperado <= 20 (baseline 12).'
    )


# ═══════════════════════════════════════════════════════════════════════
# 4. vacaciones/vacaciones_panel
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_vacaciones_panel_no_n_plus_1(admin_client, personal_10):
    """vacaciones_panel itera solicitudes y vac_mes accediendo personal.apellidos_nombres."""
    from vacaciones.models import SolicitudVacacion, SaldoVacacional
    hoy = date.today()
    # Crear saldos + solicitudes para 5 trabajadores
    for i, p in enumerate(personal_10[:5]):
        s = SaldoVacacional.objects.create(
            personal=p,
            periodo_inicio=date(2024, 1, 1),
            periodo_fin=date(2024, 12, 31),
            dias_derecho=30,
            dias_gozados=0,
            dias_pendientes=30,
            estado='PENDIENTE',
        )
        SolicitudVacacion.objects.create(
            personal=p,
            saldo=s,
            fecha_inicio=hoy + timedelta(days=i),
            fecha_fin=hoy + timedelta(days=i + 5),
            dias_calendario=6,
            estado='APROBADA' if i % 2 else 'PENDIENTE',
        )

    url = reverse('vacaciones_panel')
    admin_client.get(url)
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as ctx:
        r = admin_client.get(url)
    assert r.status_code == 200
    nq = len(ctx.captured_queries)
    # Baseline: 15 queries (sidebar + solicitudes + count + 5 stats + 3 solicitud
    # querysets distintos para vac_mes/vac_proximas/dist + top_areas).
    # solicitudes/vac_mes/vac_proximas iteran 5 trabajadores accediendo
    # personal.apellidos_nombres pero los 3 usan select_related('personal') → sin N+1.
    assert nq <= 22, (
        f'vacaciones_panel hizo {nq} queries — esperado <= 22 (baseline 15).'
    )


# ═══════════════════════════════════════════════════════════════════════
# 5. reclutamiento/pipeline_panel
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_pipeline_panel_no_n_plus_1(admin_client):
    """pipeline_panel itera postulaciones accediendo p.vacante.titulo."""
    from reclutamiento.models import Vacante, EtapaPipeline, Postulacion
    # Crear 2 vacantes + 3 etapas
    v1 = Vacante.objects.create(
        titulo='Cocinero Senior',
        descripcion='Test',
        estado='PUBLICADA',
    )
    v2 = Vacante.objects.create(
        titulo='Cajero',
        descripcion='Test',
        estado='PUBLICADA',
    )
    e1 = EtapaPipeline.objects.create(nombre='CV recibido', codigo='cv-perf', orden=1, activa=True)
    e2 = EtapaPipeline.objects.create(nombre='Entrevista', codigo='ent-perf', orden=2, activa=True)
    e3 = EtapaPipeline.objects.create(nombre='Oferta', codigo='of-perf', orden=3, activa=True)
    etapas = [e1, e2, e3]
    # 10 postulaciones activas
    for i in range(10):
        Postulacion.objects.create(
            vacante=v1 if i % 2 else v2,
            etapa=etapas[i % 3],
            nombre_completo=f'Candidato {i}',
            email=f'c{i}@ex.com',
            estado='ACTIVA',
            cv_score=70 + i,
        )

    url = reverse('pipeline_panel')
    admin_client.get(url)
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as ctx:
        r = admin_client.get(url)
    assert r.status_code == 200
    nq = len(ctx.captured_queries)
    # Baseline: 8 queries (sidebar + etapas + postulaciones + ultimas_notas_pl + vacantes_activas).
    # postulaciones itera 10 candidatos accediendo p.vacante.titulo → select_related lo cubre.
    assert nq <= 15, (
        f'pipeline_panel hizo {nq} queries — esperado <= 15 (baseline 8).'
    )


# ═══════════════════════════════════════════════════════════════════════
# Sentinel: si quitan select_related, el test ataja la regresión
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_personal_list_select_related_still_in_place(admin_client, personal_10):
    """Sentinel: si alguien quita el .select_related() de personal_list,
    aumenta drásticamente el query count. Este test es la barrera de
    último recurso si el threshold absoluto de arriba se ajusta mal.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    url = reverse('personal_list')
    admin_client.get(url)  # warm-up
    with CaptureQueriesContext(connection) as ctx:
        admin_client.get(url)
    # Sin select_related, con 10 personas en 3 subáreas y user_superuser, el
    # template haría 10 queries extra por p.subarea.nombre. Con select_related,
    # los queries permanecen estables.
    queries_sql = [q['sql'] for q in ctx.captured_queries]
    # Contar queries SELECT en personal_subarea (la FK accedida en el template)
    # Si select_related está activo, hay 1 sola query (JOIN), no múltiples lookups
    subarea_lookups = sum(
        1 for sql in queries_sql
        if 'personal_subarea' in sql.lower() and 'where' in sql.lower() and ' = ' in sql.lower()
    )
    # Debe haber 0-1 (filtros del dropdown), NUNCA 10
    assert subarea_lookups < 5, (
        f'Demasiados SELECT en personal_subarea ({subarea_lookups}) — '
        f'probable N+1: alguien quitó select_related en personal_list'
    )
