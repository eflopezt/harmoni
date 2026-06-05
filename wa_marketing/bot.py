"""
Máquina de estados del bot conversacional de Harmoni.

Estados (WaConversacion.menu_state):
  INICIO                     → mensaje libre del cliente → menú principal
  ESPERA_DEMO_NOMBRE         → cliente respondió "1", esperando nombre
  ESPERA_DEMO_EMPRESA        → tiene nombre, esperando empresa
  ESPERA_DEMO_EMPLEADOS      → tiene empresa, esperando #empleados
                                → al recibir, crea WaLead y vuelve a INICIO

Cualquier mensaje cuando estado=HANDOFF NO ejecuta lógica del bot; solo
se guarda y queda visible en el inbox para que un humano responda.

Comando especial: el cliente puede escribir "asesor" / "humano" / "0" en
cualquier momento → pasa a HANDOFF.
"""
from __future__ import annotations

import re
from typing import Optional

from . import client
from .models import WaConversacion, WaMensaje, WaLead


MENU_PRINCIPAL_TEXT = (
    "Hola! Soy el asistente virtual de *Harmoni ERP* 🤖\n\n"
    "Somos un ERP de RRHH y Planillas hecho para empresas peruanas.\n\n"
    "¿En qué puedo ayudarte? Responde con el número:\n\n"
    "1️⃣  Solicitar una *demo gratuita*\n"
    "2️⃣  Ver *planes y precios*\n"
    "3️⃣  Conocer los *módulos*\n"
    "4️⃣  Hablar con un *asesor humano*"
)

PLANES_TEXT = (
    "*Planes Harmoni ERP* 💼\n\n"
    "🔹 *ASISTENCIA* — S/ 99/mes (hasta 50)\n"
    "   Tareo, papeletas, horas extra, reportes\n\n"
    "🔹 *PLANILLA* — S/ 199/mes (hasta 100)\n"
    "   + Nóminas, boletas, liquidación y SUNAT\n\n"
    "🔹 *TALENTO* — S/ 399/mes (hasta 300)\n"
    "   + Evaluaciones, capacitaciones, clima, analytics\n\n"
    "🔹 *SUITE* — S/ 699/mes (300+)\n"
    "   + Reclutamiento, portal del empleado e IA\n\n"
    "Asistencia y Planilla tienen *30 días gratis* (sin tarjeta).\n"
    "¿Quieres una demo? Responde *1*. Para hablar con un asesor responde *4*."
)

MODULOS_TEXT = (
    "*22 módulos de Harmoni* 📦\n\n"
    "👤 Personal · Contratos DL 728 · Organigrama\n"
    "🕐 Asistencia · Biometría · Papeletas · Banco de horas\n"
    "💰 Nóminas · IR 5ta · AFP · CTS · Gratificaciones\n"
    "🏖️ Vacaciones DL 713 · Saldos · Triple vacacional\n"
    "📄 Documentos · Firmas · Plantillas\n"
    "🎯 Reclutamiento · Onboarding · Evaluaciones 360\n"
    "📚 Capacitaciones · Encuestas clima\n"
    "🔌 PLAME · T-Registro · AFP Net · CONCAR · SAP\n\n"
    "Todo en una sola plataforma, normativa peruana al 100%.\n\n"
    "¿Quieres una demo? Responde *1*."
)

HANDOFF_TEXT = (
    "Listo, te conecto con un asesor humano 👨‍💼\n"
    "Un miembro del equipo Harmoni te responderá en breve por este mismo chat.\n\n"
    "Horario de atención: L-V 9am-7pm · Sáb 9am-1pm"
)

DEMO_INICIO_TEXT = "Perfecto! Vamos a coordinar tu demo gratuita 🚀\n\n¿Cuál es tu *nombre completo*?"
DEMO_PIDE_EMPRESA_TEXT = "Genial *{nombre}*. ¿En qué *empresa* trabajas?"
DEMO_PIDE_EMPLEADOS_TEXT = "Ok. ¿Cuántos *colaboradores* tiene la empresa aproximadamente?"
DEMO_CIERRE_TEXT = (
    "Listo *{nombre}*! ✅\n\n"
    "Registramos:\n"
    "• Empresa: {empresa}\n"
    "• Colaboradores: {empleados}\n\n"
    "Un asesor de Harmoni te contactará hoy mismo para coordinar fecha y hora de la demo.\n\n"
    "Mientras tanto puedes ver más en https://harmoni.pe 🌐"
)

# Palabras que disparan handoff inmediato
HANDOFF_KEYWORDS = {'asesor', 'humano', 'persona', 'agente', 'vendedor', 'soporte', 'ayuda urgente'}


def procesar_entrante(conv: WaConversacion, mensaje_entrante: WaMensaje) -> None:
    """
    Procesa un mensaje entrante: actualiza estado y, si corresponde, envía respuesta.
    Solo actúa si conv.estado == BOT. Si está en HANDOFF, no hace nada (humano responde).
    """
    if conv.estado != WaConversacion.ESTADO_BOT:
        return

    body = (mensaje_entrante.cuerpo or '').strip()
    body_lower = body.lower()

    # Handoff manual en cualquier estado
    if _contiene_keyword(body_lower, HANDOFF_KEYWORDS) or body_lower in {'0', '4'}:
        _ir_a_handoff(conv)
        return

    estado = conv.menu_state

    if estado == WaConversacion.MENU_INICIO:
        # Interpretar opción del menú o mandar menú si no entiende
        if body_lower in {'1', 'demo', 'solicitar demo', '1️⃣'}:
            _enviar_y_log(conv, DEMO_INICIO_TEXT)
            conv.menu_state = WaConversacion.MENU_ESPERA_DEMO_NOMBRE
            conv.save(update_fields=['menu_state', 'actualizado_en'])
        elif body_lower in {'2', 'planes', 'precios', '2️⃣'}:
            _enviar_y_log(conv, PLANES_TEXT)
        elif body_lower in {'3', 'modulos', 'módulos', '3️⃣'}:
            _enviar_y_log(conv, MODULOS_TEXT)
        else:
            _enviar_y_log(conv, MENU_PRINCIPAL_TEXT)

    elif estado == WaConversacion.MENU_ESPERA_DEMO_NOMBRE:
        nombre = _sanitizar(body, max_len=120)
        if not nombre:
            _enviar_y_log(conv, "No entendí. ¿Cuál es tu nombre completo?")
            return
        # Guardamos el nombre como nombre_wa si no había
        if not conv.nombre_wa:
            conv.nombre_wa = nombre
        WaLead.objects.update_or_create(
            telefono=conv.telefono,
            contactado=False,
            defaults={'nombre': nombre, 'conversacion': conv, 'origen': WaLead.ORIGEN_BOT_DEMO},
        )
        _enviar_y_log(conv, DEMO_PIDE_EMPRESA_TEXT.format(nombre=nombre.split()[0]))
        conv.menu_state = WaConversacion.MENU_ESPERA_DEMO_EMPRESA
        conv.save(update_fields=['nombre_wa', 'menu_state', 'actualizado_en'])

    elif estado == WaConversacion.MENU_ESPERA_DEMO_EMPRESA:
        empresa = _sanitizar(body, max_len=180)
        lead = _lead_en_curso(conv)
        if lead:
            lead.empresa = empresa
            lead.save(update_fields=['empresa'])
        _enviar_y_log(conv, DEMO_PIDE_EMPLEADOS_TEXT)
        conv.menu_state = WaConversacion.MENU_ESPERA_DEMO_EMPLEADOS
        conv.save(update_fields=['menu_state', 'actualizado_en'])

    elif estado == WaConversacion.MENU_ESPERA_DEMO_EMPLEADOS:
        empleados = _sanitizar(body, max_len=40)
        lead = _lead_en_curso(conv)
        if lead:
            lead.num_empleados = empleados
            lead.save(update_fields=['num_empleados'])
        nombre_corto = (lead.nombre.split()[0] if lead and lead.nombre else '')
        _enviar_y_log(conv, DEMO_CIERRE_TEXT.format(
            nombre=nombre_corto,
            empresa=(lead.empresa if lead else '—'),
            empleados=empleados or '—',
        ))
        conv.menu_state = WaConversacion.MENU_INICIO
        conv.save(update_fields=['menu_state', 'actualizado_en'])

    else:
        # Estado desconocido — resetear
        _enviar_y_log(conv, MENU_PRINCIPAL_TEXT)
        conv.menu_state = WaConversacion.MENU_INICIO
        conv.save(update_fields=['menu_state', 'actualizado_en'])


def _ir_a_handoff(conv: WaConversacion) -> None:
    _enviar_y_log(conv, HANDOFF_TEXT)
    conv.estado = WaConversacion.ESTADO_HANDOFF
    conv.menu_state = WaConversacion.MENU_INICIO
    conv.save(update_fields=['estado', 'menu_state', 'actualizado_en'])


def _enviar_y_log(conv: WaConversacion, texto: str) -> None:
    """Envía vía sidecar y graba el saliente en la DB."""
    resultado = client.send_text(conv.telefono, texto)
    WaMensaje.objects.create(
        conversacion=conv,
        direccion=WaMensaje.DIR_OUT,
        tipo=WaMensaje.TIPO_TEXTO,
        cuerpo=texto,
        wa_message_id=resultado.get('id') or '',
    )


def _lead_en_curso(conv: WaConversacion) -> Optional[WaLead]:
    return conv.leads.filter(contactado=False).order_by('-creado_en').first()


def _contiene_keyword(text: str, keywords: set) -> bool:
    for kw in keywords:
        if kw in text:
            return True
    return False


def _sanitizar(text: str, max_len: int) -> str:
    text = re.sub(r'\s+', ' ', text or '').strip()
    return text[:max_len]
