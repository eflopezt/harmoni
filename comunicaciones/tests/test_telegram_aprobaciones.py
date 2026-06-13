"""
Tests de aprobaciones por Telegram (webhook + signals + acciones).

Cubre:
- Webhook: sin TELEGRAM_WEBHOOK_SECRET → 403; secret incorrecto → 403.
- Callback "aprobar vacación" del chat autorizado → SolicitudVacacion
  APROBADA con aprobado_por = superuser; se responde y edita el mensaje.
- Callback de chat NO autorizado → no toca nada.
- Solicitud ya resuelta → no se re-aprueba.
- Signal: crear Prestamo PENDIENTE dispara el envío con botones.
"""
import json
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from comunicaciones import telegram_aprobaciones as tg
from personal.models import Area, Personal, SubArea
from vacaciones.models import SolicitudVacacion

WEBHOOK = "/comunicaciones/telegram/webhook/"
CHAT = "2071138853"


@pytest.fixture
def subarea(db):
    area = Area.objects.create(nombre="Ops")
    return SubArea.objects.create(nombre="Campo", area=area)


@pytest.fixture
def trabajador(subarea):
    return Personal.objects.create(
        nro_doc="71000095", apellidos_nombres="TELE, GRAMA",
        cargo="Op", tipo_trab="Empleado", estado="Activo",
        subarea=subarea, fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal("2000.00"),
    )


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser("jefa", "j@h.pe", "x")


@pytest.fixture
def tg_config(monkeypatch):
    """Config Telegram simulada + captura de llamadas a la Bot API."""
    llamadas = []
    monkeypatch.setattr(tg, "_config", lambda: ("token-test", CHAT))
    monkeypatch.setattr(tg, "_post", lambda metodo, payload, token:
                        llamadas.append((metodo, payload)) or {"ok": True, "result": {}})
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secreto-123")
    return llamadas


def _callback(data, chat_id=CHAT):
    return {
        "callback_query": {
            "id": "cbq1",
            "data": data,
            "message": {"message_id": 77, "chat": {"id": int(chat_id)}},
        }
    }


def _solicitud(trabajador):
    return SolicitudVacacion.objects.create(
        personal=trabajador, fecha_inicio=date(2026, 7, 1),
        fecha_fin=date(2026, 7, 7), dias_calendario=7, estado="PENDIENTE",
    )


class TestWebhookSeguridad:
    def test_sin_secret_en_entorno_403(self, client, db, monkeypatch):
        monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
        resp = client.post(WEBHOOK, "{}", content_type="application/json")
        assert resp.status_code == 403

    def test_secret_incorrecto_403(self, client, db, tg_config):
        resp = client.post(WEBHOOK, "{}", content_type="application/json",
                           HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="malo")
        assert resp.status_code == 403


class TestCallbacks:
    def _post_cb(self, client, payload):
        return client.post(
            WEBHOOK, json.dumps(payload), content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="secreto-123",
        )

    def test_aprobar_vacacion(self, client, tg_config, trabajador, superuser):
        sol = _solicitud(trabajador)
        resp = self._post_cb(client, _callback(f"apr:vac:{sol.pk}"))
        assert resp.status_code == 200
        assert resp.json()["resultado"] == "ok"

        sol.refresh_from_db()
        assert sol.estado == "APROBADA"
        assert sol.aprobado_por == superuser
        metodos = [m for m, _ in tg_config]
        assert "answerCallbackQuery" in metodos
        assert "editMessageText" in metodos

    def test_rechazar_vacacion(self, client, tg_config, trabajador, superuser):
        sol = _solicitud(trabajador)
        self._post_cb(client, _callback(f"rec:vac:{sol.pk}"))
        sol.refresh_from_db()
        assert sol.estado == "RECHAZADA"
        assert "Telegram" in sol.motivo_rechazo

    def test_chat_no_autorizado_no_toca_nada(self, client, tg_config, trabajador, superuser):
        sol = _solicitud(trabajador)
        resp = self._post_cb(client, _callback(f"apr:vac:{sol.pk}", chat_id="999"))
        assert resp.json()["resultado"] == "chat_no_autorizado"
        sol.refresh_from_db()
        assert sol.estado == "PENDIENTE"

    def test_ya_resuelta_no_se_reaprueba(self, client, tg_config, trabajador, superuser):
        sol = _solicitud(trabajador)
        sol.aprobar(superuser)
        otro = User.objects.create_superuser("zeta", "z@h.pe", "x")
        resp = self._post_cb(client, _callback(f"rec:vac:{sol.pk}"))
        assert resp.json()["resultado"] == "ya_resuelta"
        sol.refresh_from_db()
        assert sol.estado == "APROBADA"
        assert sol.aprobado_por != otro


class TestSignals:
    def test_prestamo_pendiente_dispara_envio(self, tg_config, trabajador):
        from prestamos.models import Prestamo, TipoPrestamo
        tipo, _ = TipoPrestamo.objects.get_or_create(
            codigo="pt-tg", defaults={"nombre": "PT"})
        Prestamo.objects.create(
            personal=trabajador, tipo=tipo,
            monto_solicitado=Decimal("400.00"), num_cuotas=2,
            estado="PENDIENTE",
        )
        envios = [p for m, p in tg_config if m == "sendMessage"]
        assert len(envios) == 1
        assert "Aprobar" in json.dumps(envios[0])
        assert f"pre:" in json.dumps(envios[0])

    def test_vacacion_borrador_no_dispara(self, tg_config, trabajador):
        SolicitudVacacion.objects.create(
            personal=trabajador, fecha_inicio=date(2026, 8, 1),
            fecha_fin=date(2026, 8, 5), dias_calendario=5, estado="BORRADOR",
        )
        assert not [p for m, p in tg_config if m == "sendMessage"]
