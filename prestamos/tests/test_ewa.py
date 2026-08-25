"""
Tests del adelanto de sueldo sobre devengado (EWA — prestamos/ewa.py).

Cubre:
- ciclo_en_curso: día 22+ pertenece al período del mes siguiente.
- calcular_disponible: devengado = días transcurridos − faltas; tope 50%;
  los adelantos vivos del ciclo reducen el disponible.
- solicitar_adelanto: crea Prestamo PENDIENTE de 1 cuota sin interés;
  rechaza montos sobre el disponible o bajo el mínimo.
- Vista del portal: el trabajador vinculado solicita; sin vínculo no rompe.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from personal.models import Area, Personal, SubArea
from prestamos import ewa
from prestamos.models import Prestamo


@pytest.fixture
def subarea(db):
    area = Area.objects.create(nombre="Operaciones")
    return SubArea.objects.create(nombre="Campo", area=area)


@pytest.fixture
def trabajador(subarea):
    # Sueldo 3000 → S/100 por día.
    return Personal.objects.create(
        nro_doc="71234567",
        apellidos_nombres="LOPEZ GARCIA, CARLOS",
        cargo="Operario",
        tipo_trab="Empleado",
        estado="Activo",
        subarea=subarea,
        fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal("3000.00"),
    )


HOY = date(2026, 6, 11)  # ciclo 22-may → 21-jun: 21 días transcurridos


class TestCicloEnCurso:
    def test_dia_dentro_del_ciclo(self):
        ciclo, (anio, mes) = ewa.ciclo_en_curso(date(2026, 6, 11))
        assert (anio, mes) == (2026, 6)
        assert ciclo.fecha_inicio == date(2026, 5, 22)
        assert ciclo.fecha_fin == date(2026, 6, 21)

    def test_dia_22_abre_el_ciclo_siguiente(self):
        ciclo, (anio, mes) = ewa.ciclo_en_curso(date(2026, 6, 22))
        assert (anio, mes) == (2026, 7)
        assert ciclo.fecha_inicio == date(2026, 6, 22)

    def test_diciembre_22_cruza_de_anio(self):
        _, (anio, mes) = ewa.ciclo_en_curso(date(2026, 12, 25))
        assert (anio, mes) == (2027, 1)


class TestCalcularDisponible:
    def test_devengado_y_tope(self, trabajador):
        info = ewa.calcular_disponible(trabajador, hoy=HOY)
        # 22-may → 11-jun = 21 días × S/100 = S/2100; tope 50% = S/1050.
        assert info["dias_devengados"] == 21
        assert info["devengado"] == Decimal("2100.00")
        assert info["tope"] == Decimal("1050.00")
        assert info["disponible"] == Decimal("1050.00")

    def test_faltas_reducen_devengado(self, trabajador):
        from asistencia.models import RegistroTareo, TareoImportacion
        imp = TareoImportacion.objects.create(
            tipo="RELOJ",
            periodo_inicio=date(2026, 5, 22), periodo_fin=date(2026, 6, 21),
        )
        RegistroTareo.objects.create(
            importacion=imp, personal=trabajador, dni=trabajador.nro_doc,
            grupo="STAFF", fecha=date(2026, 6, 1), codigo_dia="FA",
        )
        info = ewa.calcular_disponible(trabajador, hoy=HOY)
        assert info["dias_devengados"] == 20
        assert info["devengado"] == Decimal("2000.00")

    def test_adelanto_vivo_reduce_disponible(self, trabajador):
        ewa.solicitar_adelanto(trabajador, "400.00", hoy=HOY)
        info = ewa.calcular_disponible(trabajador, hoy=HOY)
        assert info["comprometido"] == Decimal("400.00")
        assert info["disponible"] == Decimal("650.00")

    def test_adelanto_rechazado_no_compromete(self, trabajador):
        p = ewa.solicitar_adelanto(trabajador, "400.00", hoy=HOY)
        p.estado = "RECHAZADO"
        p.save(update_fields=["estado"])
        info = ewa.calcular_disponible(trabajador, hoy=HOY)
        assert info["disponible"] == Decimal("1050.00")


class TestSolicitarAdelanto:
    def test_crea_prestamo_pendiente_una_cuota(self, trabajador):
        p = ewa.solicitar_adelanto(trabajador, "500.00", hoy=HOY)
        assert p.estado == "PENDIENTE"
        assert p.num_cuotas == 1
        assert p.tasa_interes == Decimal("0.000")
        assert p.tipo.codigo == ewa.TIPO_CODIGO
        assert p.monto_solicitado == Decimal("500.00")

    def test_rechaza_monto_sobre_disponible(self, trabajador):
        with pytest.raises(ewa.EWAError, match="supera"):
            ewa.solicitar_adelanto(trabajador, "1050.01", hoy=HOY)

    def test_rechaza_monto_bajo_minimo(self, trabajador):
        with pytest.raises(ewa.EWAError, match="mínimo"):
            ewa.solicitar_adelanto(trabajador, "10.00", hoy=HOY)

    def test_rechaza_sin_sueldo_base(self, subarea):
        p = Personal.objects.create(
            nro_doc="79999999", apellidos_nombres="SIN SUELDO, X",
            cargo="Operario", tipo_trab="Empleado", estado="Activo",
            subarea=subarea, fecha_alta=date(2024, 1, 1),
            sueldo_base=Decimal("0"),
        )
        with pytest.raises(ewa.EWAError, match="sueldo"):
            ewa.solicitar_adelanto(p, "100.00", hoy=HOY)

    def test_segundo_adelanto_respeta_disponible_restante(self, trabajador):
        ewa.solicitar_adelanto(trabajador, "1000.00", hoy=HOY)
        with pytest.raises(ewa.EWAError):
            ewa.solicitar_adelanto(trabajador, "100.00", hoy=HOY)  # quedan 50 < 100... ok
        p2 = ewa.solicitar_adelanto(trabajador, "50.00", hoy=HOY)
        assert p2.monto_solicitado == Decimal("50.00")


class TestVistaPortal:
    @pytest.fixture
    def user_vinculado(self, trabajador):
        user = User.objects.create_user("carlos", password="x")
        trabajador.usuario = user
        trabajador.save(update_fields=["usuario"])
        return user

    def test_get_muestra_disponible(self, client, user_vinculado):
        client.login(username="carlos", password="x")
        resp = client.get(reverse("portal_mi_adelanto"))
        assert resp.status_code == 200
        assert b"Disponible" in resp.content

    def test_post_crea_solicitud(self, client, user_vinculado, trabajador):
        client.login(username="carlos", password="x")
        # La disponibilidad cambia cada dia dentro del ciclo 22→21. Usar un
        # monto valido para la fecha real evita que el test venza con el mes.
        disponible = ewa.calcular_disponible(trabajador)['disponible']
        monto = min(Decimal('300.00'), disponible)
        assert monto >= ewa.MONTO_MINIMO
        resp = client.post(reverse("portal_mi_adelanto"), {"monto": str(monto), "motivo": "test"})
        assert resp.status_code == 302
        p = Prestamo.objects.get(personal=trabajador, tipo__codigo=ewa.TIPO_CODIGO)
        assert p.estado == "PENDIENTE"
        assert p.solicitado_por == user_vinculado

    def test_usuario_sin_vinculo_no_rompe(self, client, db):
        User.objects.create_user("suelto", password="x")
        client.login(username="suelto", password="x")
        resp = client.get(reverse("portal_mi_adelanto"))
        assert resp.status_code == 200
