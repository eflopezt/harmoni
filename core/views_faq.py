"""
FAQs públicas para clientes gastronómicos.

URL: /faq/
"""
from django.shortcuts import render


FAQ_GASTRO = [
    {
        'categoria': '🍽️ Propinas y recargo',
        'items': [
            {
                'q': '¿Harmoni maneja las propinas correctamente?',
                'a': 'Sí. Las propinas son concepto NO remunerativo (D.S. 003-2018-TR) — no entran al cálculo de CTS ni gratificaciones. Harmoni las registra en una columna separada en la boleta y planilla para que sean visibles pero no inflar el costo laboral.',
            },
            {
                'q': '¿Cómo manejan el recargo por consumo?',
                'a': 'El recargo por consumo de 10% es ingreso NO remunerativo según norma. Harmoni soporta carga mensual fija (regular) y variable (quincenal según facturación). Va a una línea de "Recargo consumo" en boleta.',
            },
        ]
    },
    {
        'categoria': '🌙 Turnos rotativos y jornada nocturna',
        'items': [
            {
                'q': '¿Calculan correctamente la jornada nocturna 22:00-06:00?',
                'a': 'Sí. Aplicamos el sobrecargo del 35% para horas dentro de la franja 22:00-06:00 (D.Leg. 854 art. 8). El sistema detecta automáticamente al cargar marcaciones y calcula la diferencial. Caso típico gastronomía: cierre 18:00-02:00.',
            },
            {
                'q': '¿Qué pasa con turnos que cruzan medianoche?',
                'a': 'Harmoni los reconoce como UN solo turno (no dos días). El cálculo de descanso semanal, horas extras, recargo nocturno todo respeta el cruce. Probado con turnos típicos de salón y cocina.',
            },
            {
                'q': '¿Y los turnos rotativos semana a semana?',
                'a': 'Sí. La Cuadrícula Semanal permite asignar a un mismo trabajador distintos turnos cada semana con drag&drop. El sistema valida descanso entre turnos (mínimo 12 horas legales).',
            },
        ]
    },
    {
        'categoria': '🏢 Multi-empresa (multi-RUC)',
        'items': [
            {
                'q': 'Tenemos 24 RUCs en distintas razones sociales. ¿Pueden manejarlo?',
                'a': 'Sí. Harmoni es multi-tenant nativo a nivel fila. Cada RUC tiene su propia configuración SUNAT, su plan de cuentas, su asiento contable. El dueño ve todo consolidado, contabilidad lo ve separado.',
            },
            {
                'q': '¿Un trabajador puede estar en varias empresas del grupo?',
                'a': 'Sí, con cuenta separada por empresa. Los aportes ESSALUD/AFP se calculan sobre cada empresa por separado (norma SUNAT) pero el sistema avisa si hay sobre-tope acumulado.',
            },
        ]
    },
    {
        'categoria': '📋 PLAME, T-Registro, AFPnet',
        'items': [
            {
                'q': '¿Generan PLAME directo desde el sistema?',
                'a': 'Sí, archivo plano formato SUNAT listo para subir al PDT 601. Genera por empresa con un click. Incluye cabecera, ingresos, descuentos y aportes.',
            },
            {
                'q': '¿Y T-Registro (altas/bajas)?',
                'a': 'Sí. Al dar de alta o cesar un trabajador, Harmoni prepara el archivo T-Registro y lo descarga listo para SUNAT. Histórico de envíos guardado.',
            },
            {
                'q': '¿AFPnet con las tasas actualizadas 2026?',
                'a': 'Sí. Las tasas AFP de las 4 AFPs (Integra, Prima, Habitat, Profuturo) están en config. Generan AFPnet directo. Si suben tasas en el futuro, hay panel admin para actualizar sin redeploy.',
            },
        ]
    },
    {
        'categoria': '💰 Planilla y cálculos peruanos',
        'items': [
            {
                'q': '¿Calculan gratificaciones (julio/diciembre)?',
                'a': 'Sí. Ley 27735, fórmula completa: meses computables, asignación familiar, bonificación 9% extraordinaria (no afecta ESSALUD por ley). Boleta separada de la regular.',
            },
            {
                'q': '¿CTS (mayo/noviembre)?',
                'a': 'Sí. Cálculo con remuneración computable (sueldo + asig fam + horas extras promedio últimos 6 meses + 1/6 gratif). Constancia de depósito generada para presentar al banco.',
            },
            {
                'q': '¿Liquidación al cese?',
                'a': 'Sí. Calcula automáticamente: CTS por cese, gratif trunca, vacaciones truncas (compensadas si hay saldo), beneficios pendientes. PDF firmable. Ver demo de un caso real en el sistema.',
            },
        ]
    },
    {
        'categoria': '📱 Portal del trabajador',
        'items': [
            {
                'q': '¿Mis mozos pueden ver sus boletas desde el celular?',
                'a': 'Sí. Portal mobile-first. Cada trabajador entra con su DNI y ve su info: boletas con QR de verificación, banco de horas, vacaciones pendientes, préstamos. Cero llamadas a RRHH.',
            },
            {
                'q': '¿Cumple con DS 009-2011-TR (constancia electrónica)?',
                'a': 'Sí. Cuando el trabajador abre su boleta, queda registrado el acuse (fecha, IP, hash). La constancia electrónica reemplaza la firma física. Auditable.',
            },
        ]
    },
    {
        'categoria': '🤖 IA y automatización',
        'items': [
            {
                'q': '¿Cómo me ayuda la IA?',
                'a': '5 modelos integrados: (1) Score de match en reclutamiento, (2) Predictor de rotación, (3) AI Summary de CVs, (4) Explicación de boleta al trabajador, (5) Asistente conversacional para gerencia.',
            },
            {
                'q': '¿Mis datos sensibles van a OpenAI?',
                'a': 'Por defecto, no. Usamos Gemini de Google (cumple norma EU + Perú) y DeepSeek (China, alta perfomance) con anonimización. OpenAI opcional. Solo metadatos del CV/perfil; NO se envían DNIs ni montos.',
            },
        ]
    },
]


def faq_publica(request):
    """Vista pública de FAQs gastronomía."""
    return render(request, 'faq/index.html', {
        'categorias':       FAQ_GASTRO,
        'total_preguntas':  sum(len(c['items']) for c in FAQ_GASTRO),
    })
