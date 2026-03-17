"""
seed_knowledge.py — Carga la base de conocimiento inicial para Harmoni AI.

Ejecutar: python manage.py seed_knowledge
Ejecutar (forzar actualización): python manage.py seed_knowledge --force

Incluye:
  - Ley laboral peruana (DL 728, DL 713, DS 003-97-TR)
  - Beneficios sociales (CTS, Gratificaciones, AFP/ONP, ESSALUD)
  - Jornada y horas extra (25%/35%/100%)
  - Vacaciones y permisos (tipos Perú)
  - Procedimiento disciplinario
  - Políticas RRHH internas de Harmoni
  - Procesos del sistema Harmoni
  - Liquidación y cese laboral (gratificación trunca, CTS trunca, indemnización)
  - Licencias especiales (maternidad, paternidad, lactancia, descanso médico)
  - PLAME, T-Registro y obligaciones SUNAT
  - Regímenes atípicos y teletrabajo
  - Guías operativas del sistema Harmoni
"""
from django.core.management.base import BaseCommand
from core.models import KnowledgeArticle

ARTICLES = [

    # ══════════════════════════════════════════════════════════════
    # LEY LABORAL PERÚ
    # ══════════════════════════════════════════════════════════════
    {
        'titulo': 'Horas Extra — Porcentajes y Reglas (DL 713, Art. 10)',
        'categoria': 'ley_laboral',
        'prioridad': 1,
        'tags': 'horas extra, sobretiempo, 25%, 35%, 100%, he, feriado, domingo, artículo 10',
        'contenido': '''\
**D.Leg. 713, Art. 10 — Remuneración por Trabajo Extraordinario:**
- Las primeras **2 horas extra** al día se pagan con **25% de sobretasa** sobre la RB.
- Desde la **3.ª hora extra** en adelante: **35% de sobretasa**.
- Trabajo en **día de descanso** (domingo/DSO): **100% de sobretasa** (doble pago).
- Trabajo en **feriado nacional**: **100% de sobretasa** + remuneración ordinaria.
- Las HE son **voluntarias**. El empleador no puede obligar salvo causa fortuita o fuerza mayor.
- El empleado puede compensar HE con **descanso sustitutorio** en lugar de pago (acuerdo por escrito).

**En Harmoni:**
- STAFF → HE van a Banco de Horas (compensación).
- RCO → HE se pagan en nómina del periodo.
- Personal de confianza/dirección: SIN control de HE ni faltas.
''',
    },

    {
        'titulo': 'Jornada Laboral Máxima — DL 854',
        'categoria': 'ley_laboral',
        'prioridad': 1,
        'tags': 'jornada, 8 horas, 48 horas semanales, dl 854, jornada máxima',
        'contenido': '''\
**D.Leg. 854 — Jornada de Trabajo:**
- Jornada máxima ordinaria: **8 horas diarias** o **48 horas semanales**.
- El empleador puede establecer jornadas menores (por empresa o área).
- Jornada nocturna (10 pm – 6 am): remuneración mínima = **RMV + 35%** (nocturno).
- La RMV vigente en Perú es **S/ 1,130** (desde enero 2025, DS 006-2024-TR).
- Si el trabajador labora más de 5 horas continuas: derecho a **refrigerio no menor a 45 min** (no computable).
''',
    },

    {
        'titulo': 'Faltas y Tardanzas — Tipos y Consecuencias (DL 728)',
        'categoria': 'ley_laboral',
        'prioridad': 2,
        'tags': 'falta, tardanza, abandono, inasistencia, dl 728, artículo 25',
        'contenido': '''\
**D.Leg. 728, Art. 25 — Faltas Graves del Trabajador:**
- **Abandono de trabajo** > 3 días consecutivos SIN justificación = falta grave → despido justificado.
- **Ausentismo injustificado** > 5 días en 30 días o > 15 días en 180 días = falta grave.
- Tardanzas reiteradas SIN justificación pueden ser sancionadas progresivamente.

**Descuentos por tardanza/falta:**
- Falta sin goce: descuento proporcional al día (sueldo ÷ 30 × días faltados).
- Tardanza: descuento por minutos/horas según política interna.

**SS (Sin Salida) en Harmoni:** día pagado, sin HE, sin descuento.
''',
    },

    {
        'titulo': 'Tipos de Contrato Laboral en Perú (DL 728)',
        'categoria': 'ley_laboral',
        'prioridad': 2,
        'tags': 'contrato, plazo fijo, plazo indeterminado, locación, intermitente, temporal, obra',
        'contenido': '''\
**Tipos de contrato más comunes (DL 728):**
- **Plazo indeterminado**: más protección, requiere causa para despedir.
- **Obra o servicio**: hasta máx. **5 años** (acumulado en mismo empleador).
- **Temporada**: trabajo en épocas específicas (campañas, proyectos estacionales).
- **Intermitente**: prestación discontinua sin plazo fijo.
- **Período de prueba**: 3 meses estándar, hasta 6 meses para trabajadores de confianza, hasta 1 año para puestos de dirección.
- Contratos a plazo fijo deben constar por escrito y registrarse en T-Registro (SUNAT) dentro de **15 días calendario**.
''',
    },

    # ══════════════════════════════════════════════════════════════
    # BENEFICIOS SOCIALES
    # ══════════════════════════════════════════════════════════════
    {
        'titulo': 'Gratificaciones de Julio y Diciembre (Ley 27735)',
        'categoria': 'beneficios',
        'prioridad': 1,
        'tags': 'gratificación, julio, diciembre, fiestas patrias, navidad, ley 27735, bonificación extraordinaria',
        'contenido': '''\
**Ley 27735 — Gratificaciones:**
- **Julio** (Fiestas Patrias): se paga en la **primera quincena de julio**.
  - Periodo de cómputo: **enero – junio** (6 meses).
- **Diciembre** (Navidad): se paga en la **primera quincena de diciembre**.
  - Periodo de cómputo: **julio – diciembre** (6 meses).
- Monto: equivale a **1 sueldo bruto** por gratificación completa (si laboró los 6 meses completos).
- Si laboró menos de 6 meses: proporcional (meses completos laborados ÷ 6 × sueldo).
- **Inafectas** a AFP/ONP y EsSalud desde Ley 29351 (y su prórroga indefinida).
- **Bonificación extraordinaria**: empresa paga 9% (EsSalud) al trabajador como bono adicional.
''',
    },

    {
        'titulo': 'CTS — Compensación por Tiempo de Servicios (D.Leg. 650)',
        'categoria': 'beneficios',
        'prioridad': 1,
        'tags': 'cts, compensación tiempo servicios, noviembre, mayo, dl 650, depósito',
        'contenido': '''\
**D.Leg. 650 — CTS:**
- Depósitos **semestrales**: **mayo** (cómputo oct–mar) y **noviembre** (cómputo abr–sep).
- Fecha límite de depósito: **15 de mayo** y **15 de noviembre**.
- Monto por semestre: 1/6 de sueldo bruto mensual × meses laborados en el periodo.
  - Base: remuneración ordinaria + 1/6 de gratificación ordinaria.
- Depósito en cuenta bancaria del trabajador (banco de su elección).
- Es **intangible**: el trabajador no puede disponer mientras esté empleado (salvo causales específicas: desempleo ≥ 1 mes, enfermedad, educación de hijos).
- Al cese: el trabajador puede retirar el 100% de su CTS.
''',
    },

    {
        'titulo': 'AFP y ONP — Sistema Previsional Perú',
        'categoria': 'beneficios',
        'prioridad': 2,
        'tags': 'afp, onp, pensión, aporte, spp, snp, 13%, habitat, prima, integra, profuturo',
        'contenido': '''\
**Sistema Previsional Peruano:**

**AFP (Sistema Privado de Pensiones — SPP):**
- Aporte obligatorio: **10%** de la remuneración sobre el total computable (sobre bruto).
- Más comisión AFP: ~1.47% (flujo) o ~1.10% (mixta) según AFP.
- Más prima de seguro: ~1.74% (seguro de invalidez, sobrevivencia y gastos de sepelio).
- Las 4 AFP vigentes: Habitat, Prima, Integra, Profuturo.

**ONP (Sistema Nacional de Pensiones — SNP):**
- Aporte: **13%** sobre la remuneración.
- Administrado por el Estado.
- Pensión máxima: S/ 893.

**EsSalud:**
- Aporte del **empleador**: **9%** de la remuneración del trabajador.
- No lo descuenta el trabajador, lo paga la empresa.
''',
    },

    {
        'titulo': 'Asignación Familiar (Ley 25129)',
        'categoria': 'beneficios',
        'prioridad': 3,
        'tags': 'asignación familiar, 10% rmv, hijos, menores',
        'contenido': '''\
**Ley 25129 — Asignación Familiar:**
- Equivale al **10% de la RMV** vigente = S/ 113.00 (con RMV de S/ 1,130).
- Aplica a trabajadores con hijos **menores de 18 años** o hasta **24 años** si estudian.
- Se paga mensualmente junto con la remuneración.
- No está afecta a descuentos ni forma parte de la base de CTS/gratificación (es un concepto separado).
''',
    },

    # ══════════════════════════════════════════════════════════════
    # VACACIONES Y PERMISOS
    # ══════════════════════════════════════════════════════════════
    {
        'titulo': 'Vacaciones — 30 Días por Año (D.Leg. 713)',
        'categoria': 'vacaciones',
        'prioridad': 1,
        'tags': 'vacaciones, 30 días, año laboral, récord vacacional, goce, venta de vacaciones',
        'contenido': '''\
**D.Leg. 713 — Vacaciones:**
- **30 días calendario** de descanso por cada año completo de servicios.
- Se genera el **récord vacacional** al cumplir 1 año de trabajo + período de calificación.
- El empleado tiene derecho a gozarlas dentro del **siguiente año** de generado el récord.
- **Acuerdo de oportunidad**: el empleador puede fijar el período de goce, respetando la razonabilidad.
- **Venta de vacaciones**: se pueden "vender" hasta **15 días** (recibir pago en lugar de descanso), pero debe gozar al menos 15 días.
- Vacaciones truncas: si el empleado cesa antes de cumplir el año, tiene derecho a pago proporcional (1/12 × meses laborados).

**En Harmoni:** solicitudes de vacaciones en módulo Vacaciones → Solicitudes → Aprobación por jefe.
''',
    },

    {
        'titulo': 'Permisos y Licencias — 12 Tipos en Perú',
        'categoria': 'vacaciones',
        'prioridad': 2,
        'tags': 'permiso, licencia, maternidad, paternidad, sindicato, luto, matrimonio, capacitación',
        'contenido': '''\
**Permisos remunerados más comunes (Perú):**
- **Licencia de maternidad**: 49 días prenatal + 49 días postnatal = 98 días (Ley 26790).
- **Licencia de paternidad**: 10 días calendario desde el nacimiento (Ley 29409).
- **Licencia por luto**: 5 días por fallecimiento de padres, cónyuge, hijos, hermanos (algunos convenios amplían).
- **Licencia sindical**: horas sindicales según convenio colectivo.
- **Permiso por matrimonio**: 5 días hábiles (políticas internas; la ley no obliga pero es práctica).
- **Licencia por enfermedad grave de familiar**: según certificado médico, a cuenta de vacaciones o sin goce.
- **Permiso por capacitación**: a criterio del empleador.

**Permisos sin goce de haber:**
- No pagan remuneración; descontados en planilla.
- No generan HE ni faltas — son días autorizados.
''',
    },

    # ══════════════════════════════════════════════════════════════
    # FERIADOS NACIONALES PERÚ
    # ══════════════════════════════════════════════════════════════
    {
        'titulo': 'Feriados Nacionales Perú 2025–2026',
        'categoria': 'asistencia',
        'prioridad': 2,
        'tags': 'feriados, feriado, festivo, días feriados, nacional, 2025, 2026',
        'contenido': '''\
**Feriados Nacionales Perú (D.Leg. 713, Art. 6):**
- 1 enero — Año Nuevo
- Semana Santa (jueves + viernes, variable)
- 1 mayo — Día del Trabajo
- 7 junio — Batalla de Arica
- 29 junio — San Pedro y San Pablo
- 28 y 29 julio — Fiestas Patrias
- 6 agosto — Batalla de Huamanga
- 30 agosto — Santa Rosa de Lima
- 8 octubre — Batalla de Angamos
- 1 noviembre — Día de Todos los Santos
- 8 diciembre — Inmaculada Concepción
- 9 diciembre — Batalla de Ayacucho
- 25 diciembre — Navidad

**Trabajar en feriado:** pago al **200%** (remuneración ordinaria + 100% sobretasa) — Art. 9, D.Leg. 713.
**En Harmoni:** los feriados se configuran en Configuración → Feriados.
''',
    },

    # ══════════════════════════════════════════════════════════════
    # PROCEDIMIENTO DISCIPLINARIO
    # ══════════════════════════════════════════════════════════════
    {
        'titulo': 'Procedimiento Disciplinario — DS 003-97-TR',
        'categoria': 'disciplinaria',
        'prioridad': 1,
        'tags': 'disciplinaria, despido, amonestación, descargo, suspensión, falta grave, ds 003-97-tr',
        'contenido': '''\
**DS 003-97-TR — Proceso Disciplinario:**

**Escala de sanciones progresivas:**
1. **Amonestación verbal** (no deja registro formal).
2. **Amonestación escrita** (carta en legajo).
3. **Suspensión sin goce** (de 1 a 30 días según gravedad).
4. **Despido justificado** (solo por falta grave comprobada).

**Proceso de despido por falta grave:**
1. Detectar la falta y documentarla.
2. Emitir **carta de pre-aviso** (carta de imputación) indicando los hechos.
3. El trabajador tiene **6 días hábiles** para presentar su **descargo**.
4. Evaluar descargo.
5. Si procede: emitir **carta de despido** con causas.

**Faltas graves (Art. 25, DL 728):** incumplimiento obligaciones, abandono, actos de violencia, inasistencias injustificadas, concurrencia en estado de ebriedad, entre otras.

**En Harmoni:** módulo Disciplinaria → registra todo el proceso, descargos y resoluciones.
''',
    },

    # ══════════════════════════════════════════════════════════════
    # PLANILLA Y REMUNERACIONES
    # ══════════════════════════════════════════════════════════════
    {
        'titulo': 'IR 5ta Categoría — Impuesto a la Renta de Trabajo',
        'categoria': 'planilla',
        'prioridad': 2,
        'tags': 'ir 5ta, impuesto renta, quinta categoría, retención, sunat, lit, uit',
        'contenido': '''\
**Impuesto a la Renta 5ta Categoría (Rentas de Trabajo):**
- Aplica a trabajadores en planilla con ingresos > 7 UIT anuales.
- UIT 2024: **S/ 5,150** → 7 UIT = S/ 36,050 anuales para estar afecto.
- Tasas escalonadas:
  - Hasta 5 UIT: **8%**
  - De 5 a 20 UIT: **14%**
  - De 20 a 35 UIT: **17%**
  - De 35 a 45 UIT: **20%**
  - Más de 45 UIT: **30%**
- El empleador retiene mensualmente (proyección anual ÷ 12).
- Las gratificaciones de julio y diciembre **sí están afectas** al IR5 (a diferencia de EsSalud/AFP).
''',
    },

    {
        'titulo': 'Ciclo de Planilla en Harmoni',
        'categoria': 'planilla',
        'prioridad': 1,
        'tags': 'planilla, nómina, ciclo, periodo, día 21, día 20, cierre, apertura',
        'contenido': '''\
**Ciclo de planilla Harmoni:**
- **Inicio**: día 21 del mes anterior.
- **Cierre**: día 20 del mes actual.
- Ejemplo: Planilla de marzo = del 21 feb al 20 mar.
- Total empleados: 224 (160 STAFF + 64 RCO).
- **STAFF**: empleados en planilla mensual fija.
- **RCO**: empleados bajo régimen de construcción civil (trato diario/quincenal).
- Personal de confianza/dirección: SIN HE ni control faltas, SÍ vacaciones/grat/CTS/AFP.

**Proceso de cierre mensual (módulo Cierre):**
1. Verificar asistencia del período.
2. Calcular HE y banco de horas.
3. Revisar novedades (faltas, permisos, licencias).
4. Procesar descuentos (préstamos, adelantos).
5. Calcular beneficios (grat/CTS si corresponde).
6. Generar planilla y boletas.
''',
    },

    # ══════════════════════════════════════════════════════════════
    # PROCESOS DEL SISTEMA HARMONI
    # ══════════════════════════════════════════════════════════════
    {
        'titulo': 'Módulos de Harmoni — Guía Rápida',
        'categoria': 'proceso',
        'prioridad': 1,
        'tags': 'módulos, harmoni, sistema, menú, funcionalidades, navegación',
        'contenido': '''\
**Módulos principales de Harmoni ERP:**
- **Personal**: empleados, áreas, cargos, contratos, legajo digital.
- **Asistencia (Tareo)**: marcaciones, HE, banco de horas, importación biométrico.
- **Vacaciones**: solicitudes, saldos, permisos y licencias (12 tipos Perú).
- **Documentos**: legajo digital, constancias, boletas de pago.
- **Préstamos**: préstamos con cuotas, adelantos de sueldo.
- **Nóminas**: planilla completa, cálculo AFP/IR/EsSalud, boletas PDF.
- **Evaluaciones**: 360°, 9-Box Grid, PDI, competencias.
- **Disciplinaria**: proceso DS 003-97-TR, descargos, resoluciones.
- **Capacitaciones**: LMS, asistencia, certificaciones.
- **Encuestas**: clima laboral, eNPS, pulsos anónimos.
- **Reclutamiento**: vacantes, kanban de candidatos, entrevistas.
- **Analytics IA**: dashboard ejecutivo con análisis por IA.
- **Portal Empleado**: auto-servicio para solicitudes, recibos, permisos.
''',
    },

    {
        'titulo': 'Banco de Horas — ¿Qué es y cómo funciona?',
        'categoria': 'proceso',
        'prioridad': 2,
        'tags': 'banco horas, banco de horas, compensación, staff, he, sobretiempo',
        'contenido': '''\
**Banco de Horas en Harmoni:**
- Solo aplica a personal **STAFF** (no a RCO).
- Cuando un STAFF realiza HE, en lugar de cobrar en nómina, las horas se acumulan en su "banco".
- El empleado puede **compensar** el banco con descanso (en lugar de trabajar un día, descuenta horas del banco).
- HE en feriado/domingo = entran al banco al 100% (doble valor).
- El banco se muestra en el Portal del Empleado → Banco de Horas.
- **RCO**: SUS horas extra se pagan directamente en la nómina del periodo.
''',
    },

    # ══════════════════════════════════════════════════════════════
    # FAQ
    # ══════════════════════════════════════════════════════════════
    {
        'titulo': '¿Cómo consulto mi saldo de vacaciones?',
        'categoria': 'faq',
        'prioridad': 3,
        'tags': 'saldo vacaciones, días disponibles, portal, empleado',
        'contenido': '''\
El empleado puede consultar su saldo de vacaciones en:
- **Portal del Empleado** → sección Mis Vacaciones → pestaña Saldo Vacacional.
- Muestra: días generados, días gozados, días disponibles.

Si eres RRHH/admin:
- **Personal** → ficha del empleado → pestaña Vacaciones.
- **Vacaciones** → Saldos Vacacionales → filtrar por empleado.

Cualquier duda sobre saldos incorrectos, contactar al área de RRHH para revisión del récord vacacional.
''',
    },

    {
        'titulo': '¿Quién es personal de confianza/dirección?',
        'categoria': 'faq',
        'prioridad': 3,
        'tags': 'confianza, dirección, gerentes, sin control, sin faltas, horas extra excluidos',
        'contenido': '''\
**Personal de confianza y dirección en Harmoni:**
- Son empleados (gerentes, directores, subgerentes) que por la naturaleza de su cargo tienen autonomía.
- **NO** están sujetos a control de HE ni control de faltas/tardanzas (art. 43, DS 003-97-TR).
- **SÍ** tienen derecho a: vacaciones, gratificaciones, CTS, AFP/ONP, EsSalud.
- En Harmoni: se marcan en la ficha del empleado como "Personal de Confianza".
- Solo se reporta presencia, no se calcula sobretiempo ni se descuentan faltas.
''',
    },

    {
        'titulo': 'Roster — ¿Qué es y para qué sirve?',
        'categoria': 'faq',
        'prioridad': 4,
        'tags': 'roster, rotación, foráneo, pasajes, control proyectado, personal foráneo',
        'contenido': '''\
**Roster en Harmoni:**
- El roster es un **control proyectado de rotación** para personal foráneo (trabajan lejos de su domicilio).
- Su función principal: **planificar la compra de pasajes aéreos** con anticipación.
- **No aplica a todos los empleados** — solo al personal foráneo que rota por períodos (ej. 14x7, 21x10).
- El roster es proyectado: puede cumplirse o no (emergencias, cambios de proyecto, etc.).
- En Harmoni: módulo Personal → Roster → Planificar rotaciones.
''',
    },

    # ══════════════════════════════════════════════════════════════
    # LEY LABORAL PERÚ — AMPLIACIÓN
    # ══════════════════════════════════════════════════════════════
    {
        'titulo': 'Asignación Familiar Detallada — Ley 25129 y DS 035-90-TR',
        'categoria': 'beneficios',
        'prioridad': 1,
        'tags': 'asignación familiar, ley 25129, ds 035-90-tr, hijos, 10% rmv, requisitos, cálculo',
        'contenido': '''\
**Ley 25129 y su Reglamento DS 035-90-TR — Asignación Familiar:**

**Requisitos para percibir la asignación familiar:**
- Ser trabajador de la actividad privada con vínculo laboral vigente.
- Tener uno o más hijos **menores de 18 años** a su cargo.
- Hijos entre **18 y 24 años**: solo si cursan estudios superiores o universitarios (acreditado con constancia de matrícula vigente).
- El trabajador debe comunicar al empleador la existencia de hijos y acreditar con partida de nacimiento o DNI del menor.

**Monto y cálculo:**
- Equivale al **10% de la Remuneración Mínima Vital (RMV)** vigente.
- Con RMV 2025 de **S/ 1,130**: asignación familiar = **S/ 113.00** mensuales.
- Es un monto **único** independientemente del número de hijos (no se multiplica por hijo).
- Se paga mensualmente junto con la remuneración habitual.

**Naturaleza remunerativa:**
- La asignación familiar **SÍ tiene carácter remunerativo** (Casación Laboral 1317-2015-Lima).
- Forma parte de la base de cálculo para: gratificaciones, CTS, vacaciones, horas extra e indemnización por despido.
- Está afecta a aportes de AFP/ONP y EsSalud.
- Está afecta al Impuesto a la Renta de 5ta categoría.

**Obligaciones del empleador:**
- Pagar la asignación desde el mes siguiente a la comunicación del trabajador.
- No puede condicionar el pago a antigüedad mínima ni a tipo de contrato.
- Aplica tanto a contratos a plazo indeterminado como a plazo fijo.

**En Harmoni:** se configura como concepto remunerativo automático en Nóminas → Conceptos → Asignación Familiar. Se activa en la ficha del empleado marcando "Tiene hijos".
''',
    },

    {
        'titulo': 'Seguro de Vida Ley — D.Leg. 688',
        'categoria': 'beneficios',
        'prioridad': 2,
        'tags': 'seguro vida ley, dl 688, obligación empleador, beneficiarios, prima, 4 años',
        'contenido': '''\
**D.Leg. 688 — Seguro de Vida Ley:**

**Obligación del empleador:**
- Todo empleador está obligado a contratar un seguro de vida a favor de sus trabajadores.
- La obligación nace a partir del **inicio de la relación laboral**, aunque la ley originalmente señalaba 4 años de servicios, la jurisprudencia y el D.Leg. 1412 establecieron la obligación desde el primer día.
- El costo de la prima es **100% a cargo del empleador**.

**Cobertura:**
- **Muerte natural**: 16 remuneraciones mensuales.
- **Muerte accidental**: 32 remuneraciones mensuales.
- **Invalidez total y permanente por accidente**: 32 remuneraciones mensuales.
- La remuneración base para el cálculo es el promedio de las remuneraciones de los últimos 3 meses antes del siniestro.

**Beneficiarios (en orden de prelación):**
1. Cónyuge o conviviente e hijos menores de 18 años (o hasta 24 si estudian).
2. Padres del trabajador (a falta de los anteriores).
3. Otros dependientes designados por el trabajador.

**Prima mensual aproximada:**
- Empleados: entre 0.53% y 0.71% de la remuneración mensual.
- Obreros: entre 0.71% y 0.89% (por mayor riesgo).
- La prima se paga mensualmente a la compañía de seguros contratada.

**Incumplimiento del empleador:**
- Si no contrata el seguro y ocurre un siniestro, el empleador asume directamente el pago de los beneficios que corresponderían.
- Multas de SUNAFIL por incumplimiento: infracción grave.

**En Harmoni:** registrado en Personal → ficha del empleado → pestaña Beneficios → Seguro de Vida Ley con fecha de inicio y aseguradora.
''',
    },

    {
        'titulo': 'Gratificación Trunca — Cálculo Proporcional al Cese',
        'categoria': 'beneficios',
        'prioridad': 1,
        'tags': 'gratificación trunca, cese, proporcional, liquidación, ley 27735, cálculo',
        'contenido': '''\
**Ley 27735, Art. 7 — Gratificación Trunca:**

**¿Cuándo aplica?**
- Cuando el trabajador cesa (renuncia, despido, mutuo disenso, fin de contrato) **antes** de la fecha de pago de la gratificación ordinaria (julio o diciembre).
- Se paga como parte de la **liquidación de beneficios sociales**.

**Cálculo de la gratificación trunca:**
- Fórmula: **(Remuneración computable ÷ 6) × meses completos laborados en el semestre**.
- Solo se consideran **meses calendarios completos** dentro del periodo de cómputo.
- Periodo julio: enero a junio. Periodo diciembre: julio a diciembre.

**Ejemplo práctico:**
- Sueldo: S/ 3,000. Cese: 15 de abril.
- Periodo de cómputo para grat. julio: enero – junio.
- Meses completos laborados: enero, febrero, marzo = 3 meses.
- Gratificación trunca = (S/ 3,000 ÷ 6) × 3 = **S/ 1,500**.
- Más bonificación extraordinaria (9%): S/ 1,500 × 9% = S/ 135.
- Total gratificación trunca = **S/ 1,635**.

**Remuneración computable:**
- Básico + asignación familiar + comisiones habituales + alimentación principal.
- Se excluyen: gratificaciones extraordinarias, participación en utilidades, condiciones de trabajo.

**Plazo de pago:**
- Dentro de las **48 horas** del cese, junto con la liquidación de beneficios sociales.

**En Harmoni:** el módulo Nóminas calcula automáticamente la gratificación trunca al registrar el cese del trabajador en Personal → Cese.
''',
    },

    {
        'titulo': 'CTS Trunca — Cálculo Proporcional al Cese (D.Leg. 650)',
        'categoria': 'beneficios',
        'prioridad': 1,
        'tags': 'cts trunca, compensación, cese, proporcional, liquidación, dl 650, cálculo',
        'contenido': '''\
**D.Leg. 650 — CTS Trunca:**

**¿Cuándo aplica?**
- Cuando el trabajador cesa antes de la fecha del depósito semestral (mayo o noviembre).
- El empleador debe pagar directamente al trabajador la CTS devengada y no depositada.

**Cálculo de la CTS trunca:**
- Fórmula: **(Remuneración computable + 1/6 de última gratificación) ÷ 12 × meses y días laborados**.
- Periodo mayo: noviembre a abril. Periodo noviembre: mayo a octubre.
- Se computan meses completos y días proporcionales (días ÷ 30).

**Ejemplo práctico:**
- Sueldo: S/ 3,600. Última gratificación: S/ 3,600.
- Cese: 20 de febrero (dentro del periodo nov–abr).
- Meses completos en el periodo: noviembre, diciembre, enero = 3 meses + 20 días de febrero.
- Remuneración computable: S/ 3,600 + (S/ 3,600 ÷ 6) = S/ 3,600 + S/ 600 = S/ 4,200.
- CTS trunca = (S/ 4,200 ÷ 12) × (3 + 20/30) = S/ 350 × 3.6667 = **S/ 1,283.33**.

**Remuneración computable para CTS:**
- Básico, asignación familiar, alimentación principal otorgada en dinero, 1/6 de la última gratificación percibida.
- Se excluyen: gratificaciones extraordinarias, utilidades, condiciones de trabajo, prestaciones alimentarias (vales).

**Plazo de pago:**
- Dentro de las **48 horas** siguientes al cese.
- El empleador entrega constancia de depósito y liquidación de CTS.

**En Harmoni:** calculado automáticamente en el proceso de liquidación (Personal → Cese → Liquidación).
''',
    },

    {
        'titulo': 'Liquidación de Beneficios Sociales — Proceso Completo',
        'categoria': 'ley_laboral',
        'prioridad': 1,
        'tags': 'liquidación, beneficios sociales, cese, 48 horas, constancia, carta de liberación',
        'contenido': '''\
**Liquidación de Beneficios Sociales al Cese:**

**¿Qué comprende?**
La liquidación es el documento que detalla todos los conceptos económicos que el empleador debe pagar al trabajador al término de la relación laboral. Incluye:

1. **Remuneración pendiente**: días laborados del último mes.
2. **Gratificación trunca**: proporcional al semestre trabajado (Ley 27735).
3. **CTS trunca**: proporcional al periodo no depositado (D.Leg. 650).
4. **Vacaciones truncas**: 1/12 por cada mes completo desde el último aniversario.
5. **Vacaciones no gozadas**: si tiene periodos vacacionales acumulados sin gozar, se paga la remuneración vacacional + indemnización por falta de goce (Art. 23, DL 713).
6. **Indemnización por despido arbitrario** (si aplica): 1.5 sueldos por año, tope 12 sueldos (DL 728).
7. **Utilidades pendientes** (si la empresa distribuye y el trabajador cesó antes del reparto).

**Plazos legales:**
- La liquidación debe pagarse dentro de las **48 horas** siguientes al cese (Art. 3, DS 001-97-TR).
- El trabajador debe firmar la **constancia de liquidación** (no implica renuncia a reclamos).
- El empleador entrega la **carta de liberación de CTS** para que el trabajador retire sus fondos del banco.
- Certificado de trabajo: obligatorio, sin plazo legal explícito pero se recomienda entrega inmediata.

**Documentos a entregar:**
- Liquidación de beneficios sociales detallada.
- Carta de liberación de CTS.
- Certificado de trabajo.
- Constancia de cese para AFP/ONP.
- Boletas de pago pendientes.

**En Harmoni:** Personal → Cese → Registrar Cese → el sistema calcula automáticamente todos los conceptos y genera la liquidación en PDF.
''',
    },

    {
        'titulo': 'Despido Arbitrario — Indemnización (DL 728, Art. 34-38)',
        'categoria': 'ley_laboral',
        'prioridad': 1,
        'tags': 'despido arbitrario, indemnización, dl 728, 1.5 sueldos, tope 12, artículo 34, artículo 38',
        'contenido': '''\
**D.Leg. 728, Art. 34-38 — Despido Arbitrario e Indemnización:**

**¿Qué es el despido arbitrario?**
- Es el despido que se produce **sin causa justa** demostrada o cuando la causa alegada no se prueba en juicio.
- También se configura cuando no se respeta el procedimiento legal de despido (falta de carta de pre-aviso, no otorgar plazo de descargo).

**Indemnización por despido arbitrario (Art. 38):**
- **Contratos a plazo indeterminado**: 1.5 remuneraciones mensuales por cada año completo de servicios, con un **tope de 12 remuneraciones**.
- Fracciones de año: se pagan en dozavos y treintavos.
- Fórmula: Indemnización = Remuneración × 1.5 × años de servicio (máx. 8 años de cómputo para alcanzar el tope de 12).

**Contratos a plazo fijo (Art. 76):**
- Indemnización = remuneraciones dejadas de percibir hasta el vencimiento del contrato, con un **tope de 12 remuneraciones**.

**Remuneración computable para la indemnización:**
- Incluye: básico, asignación familiar, comisiones, alimentación principal.
- No incluye: gratificaciones, CTS, utilidades, condiciones de trabajo.

**Ejemplo práctico (plazo indeterminado):**
- Sueldo: S/ 4,000. Tiempo de servicios: 5 años y 3 meses.
- Indemnización = S/ 4,000 × 1.5 × 5 + (S/ 4,000 × 1.5 ÷ 12 × 3) = S/ 30,000 + S/ 1,500 = **S/ 31,500**.

**Protección contra despido nulo (Art. 29):**
- Es nulo el despido por: afiliación sindical, embarazo, discriminación, queja ante autoridad, discapacidad, por ser portador de VIH.
- El despido nulo se impugna judicialmente y la consecuencia es la **reposición** (no indemnización).

**En Harmoni:** módulo Disciplinaria → Tipo de cese → Despido arbitrario → calcula automáticamente la indemnización.
''',
    },

    {
        'titulo': 'Renuncia Voluntaria — Procedimiento y Plazos (DL 728)',
        'categoria': 'ley_laboral',
        'prioridad': 2,
        'tags': 'renuncia, voluntaria, preaviso, 30 días, exoneración, procedimiento, carta',
        'contenido': '''\
**D.Leg. 728 y DS 003-97-TR — Renuncia Voluntaria:**

**Procedimiento legal:**
1. El trabajador presenta **carta de renuncia** dirigida al empleador con **30 días calendario de anticipación**.
2. La carta debe indicar: fecha de presentación, fecha de cese propuesta y firma del trabajador.
3. No requiere expresar motivos ni razones.

**Exoneración del plazo de preaviso:**
- El empleador puede **exonerar** al trabajador del plazo de 30 días, total o parcialmente.
- La exoneración debe ser por escrito (carta de aceptación con exoneración).
- Si el empleador exonera, el trabajador cesa en la fecha indicada por el empleador.
- Si el empleador no se pronuncia en 3 días, se entiende **aceptada** la renuncia.

**Retiro de la renuncia:**
- El trabajador puede **retirar su carta de renuncia** mientras no haya sido aceptada por el empleador.
- Una vez aceptada (expresa o tácitamente), no puede retirarse.

**Derechos del trabajador al renunciar:**
- Liquidación de beneficios sociales completa (dentro de 48 horas).
- Certificado de trabajo.
- Carta de liberación de CTS.
- Constancia de cese para AFP.
- **No tiene derecho a indemnización** por despido (fue decisión voluntaria).

**Renuncia con incentivos:**
- El empleador puede ofrecer un pago adicional ("incentivo de renuncia" o "programa de retiro voluntario").
- Este pago es independiente de la liquidación de beneficios sociales.

**En Harmoni:** Personal → Cese → Tipo: Renuncia voluntaria → cargar carta de renuncia → sistema calcula liquidación automáticamente.
''',
    },

    {
        'titulo': 'Periodo de Prueba — Duración y Excepciones (Art. 10, DL 728)',
        'categoria': 'ley_laboral',
        'prioridad': 2,
        'tags': 'periodo de prueba, 3 meses, 6 meses, 1 año, confianza, dirección, artículo 10, dl 728',
        'contenido': '''\
**D.Leg. 728, Art. 10 — Periodo de Prueba:**

**Duración estándar:**
- **3 meses** para trabajadores comunes (empleados y obreros).
- Durante el periodo de prueba, el empleador puede resolver el contrato **sin expresar causa** y sin pagar indemnización.
- El trabajador SÍ tiene derecho a todos los beneficios durante el periodo de prueba (remuneración, CTS, gratificación proporcional, vacaciones truncas, EsSalud, AFP/ONP).

**Excepciones (periodos extendidos):**
- **Personal de confianza**: hasta **6 meses** de periodo de prueba.
- **Personal de dirección**: hasta **12 meses** (1 año) de periodo de prueba.
- La extensión debe estar pactada por escrito en el contrato de trabajo y justificada por la naturaleza del cargo.

**¿Qué pasa después del periodo de prueba?**
- El trabajador adquiere **protección contra el despido arbitrario**.
- A partir de este momento, el despido sin causa genera la obligación de pagar **indemnización** (1.5 sueldos por año, Art. 38).

**Cómputo del periodo:**
- Se cuenta desde el primer día de labores efectivas.
- No se interrumpe por descanso médico, vacaciones ni licencias.
- Los días no laborados no se descuentan del cómputo.

**Importante:**
- No se puede pactar un periodo de prueba mayor al que corresponde por ley (3, 6 o 12 meses según el caso).
- Si el contrato no menciona periodo de prueba, se aplica el de 3 meses por defecto.
- Sucesivos contratos a plazo fijo con el mismo empleador: el periodo de prueba solo se aplica al **primer contrato**.

**En Harmoni:** la ficha del empleado registra fecha de inicio y tipo de cargo, calculando automáticamente la fecha de fin del periodo de prueba.
''',
    },

    {
        'titulo': 'Venta de Vacaciones — Máximo 15 Días (DL 713, Art. 19)',
        'categoria': 'vacaciones',
        'prioridad': 2,
        'tags': 'venta vacaciones, reducción, 15 días, compensación, acuerdo, dl 713, artículo 19',
        'contenido': '''\
**D.Leg. 713, Art. 19 — Reducción de Vacaciones (Venta):**

**Marco legal:**
- El trabajador puede **convenir por escrito** con el empleador la reducción del descanso vacacional de 30 a 15 días.
- Los 15 días "vendidos" se compensan económicamente: el trabajador recibe la **remuneración vacacional** por esos días además de su sueldo normal.
- Es un acuerdo **voluntario** — el empleador no puede obligar al trabajador a vender vacaciones.

**Cálculo económico de la venta:**
- Remuneración por vacaciones gozadas (15 días): ya incluida en el sueldo mensual.
- Remuneración por vacaciones vendidas (15 días): pago adicional = sueldo ÷ 30 × 15.
- Total que percibe el trabajador en el mes de vacaciones: sueldo normal + compensación por 15 días vendidos.

**Ejemplo:**
- Sueldo: S/ 3,000.
- Goza 15 días de vacaciones y vende 15 días.
- Pago adicional por venta: S/ 3,000 ÷ 30 × 15 = **S/ 1,500**.
- El trabajador recibe en ese mes: S/ 3,000 (sueldo) + S/ 1,500 (venta) = **S/ 4,500**.

**Restricciones:**
- Mínimo **15 días** de descanso efectivo obligatorio. No se puede vender más de 15 días.
- El acuerdo debe constar por **escrito** y firmarse antes del inicio del goce vacacional.
- Si el trabajador no goza vacaciones en todo el año siguiente, se genera la **triple vacacional** (Art. 23, DL 713).

**En Harmoni:** Vacaciones → Nueva Solicitud → marcar "Incluir venta de vacaciones" → especificar días a vender (máx. 15) → aprobación del jefe y RRHH.
''',
    },

    {
        'titulo': 'Descanso Médico y Subsidio EsSalud — Primeros 20 Días',
        'categoria': 'ley_laboral',
        'prioridad': 2,
        'tags': 'descanso médico, subsidio, essalud, incapacidad temporal, 20 días, certificado, citt',
        'contenido': '''\
**Descanso Médico — Subsidio por Incapacidad Temporal (Ley 26790):**

**Primeros 20 días:**
- Los primeros **20 días** de descanso médico son pagados **íntegramente por el empleador**.
- Se paga la remuneración normal completa (no hay descuento).
- No requiere trámite ante EsSalud, solo el certificado médico.

**A partir del día 21:**
- EsSalud asume el pago mediante **subsidio por incapacidad temporal**.
- El subsidio equivale al promedio diario de las remuneraciones de los últimos 12 meses, multiplicado por los días de subsidio.
- Máximo: **11 meses y 10 días** consecutivos de subsidio.

**Requisitos para el subsidio EsSalud:**
- Tener 3 meses consecutivos de aportes o 4 meses no consecutivos en los últimos 6 meses anteriores al mes de inicio de la incapacidad.
- Contar con vínculo laboral vigente al inicio de la incapacidad.
- El CITT (Certificado de Incapacidad Temporal para el Trabajo) emitido por EsSalud o entidad autorizada.

**Procedimiento:**
1. El trabajador presenta certificado médico al empleador.
2. El empleador paga los primeros 20 días.
3. A partir del día 21, el empleador solicita el reembolso a EsSalud.
4. EsSalud evalúa y reembolsa o paga directamente al trabajador.

**Obligación del empleador:**
- No puede despedir al trabajador durante el descanso médico justificado.
- Debe reservar el puesto de trabajo.
- Si el descanso supera 12 meses, puede optar por el cese con liquidación.

**En Harmoni:** Asistencia → Papeletas → Tipo: Descanso médico → adjuntar certificado → el sistema registra días y controla el límite de 20 días del empleador.
''',
    },

    {
        'titulo': 'Licencia de Maternidad — Pre y Post Natal (Ley 26644)',
        'categoria': 'ley_laboral',
        'prioridad': 1,
        'tags': 'maternidad, prenatal, postnatal, 98 días, ley 26644, subsidio, embarazo, gestante',
        'contenido': '''\
**Ley 26644 — Licencia de Maternidad:**

**Duración:**
- **49 días de descanso prenatal** (antes del parto).
- **49 días de descanso postnatal** (después del parto).
- Total: **98 días calendario** de licencia por maternidad.

**Modificaciones opcionales:**
- La trabajadora puede diferir parcial o totalmente el descanso prenatal, acumulándolo al postnatal.
- Requiere comunicación al empleador con **2 meses de anticipación** al parto y certificado médico que acredite que no afecta la salud de la gestante ni del concebido.
- En caso de **parto múltiple**: 30 días adicionales de descanso postnatal.
- En caso de **nacimiento con discapacidad**: 30 días adicionales de postnatal (Ley 29992).

**Subsidio por maternidad (EsSalud):**
- EsSalud paga el subsidio durante los 98 días (o los extendidos).
- El subsidio equivale al promedio de las remuneraciones de los últimos 12 meses.
- Requisitos: 3 meses consecutivos o 4 no consecutivos de aportes en los 6 meses previos.

**Protección contra el despido:**
- La trabajadora gestante goza de **protección contra el despido** desde el inicio del embarazo hasta los 90 días posteriores al parto (Art. 29, inciso e, DL 728).
- El despido durante este periodo se presume **nulo** y procede la reposición.

**Obligaciones del empleador:**
- Reservar el puesto de trabajo durante toda la licencia.
- No asignar labores que pongan en riesgo la salud de la gestante.
- Conceder permisos para controles prenatales.

**En Harmoni:** Personal → ficha de la trabajadora → Licencias → Tipo: Maternidad → registrar fechas de pre y post natal → integración automática con planilla.
''',
    },

    {
        'titulo': 'Licencia de Paternidad — 10 Días (Ley 29409)',
        'categoria': 'ley_laboral',
        'prioridad': 2,
        'tags': 'paternidad, licencia, 10 días, ley 29409, padre, nacimiento, remunerada',
        'contenido': '''\
**Ley 29409 (modificada por Ley 30807) — Licencia de Paternidad:**

**Duración y tipo:**
- **10 días calendario** de licencia remunerada.
- En caso de parto múltiple o cesárea: **20 días calendario**.
- En caso de nacimiento prematuro o con enfermedad congénita terminal: **30 días calendario**.
- En caso de complicaciones graves en la salud de la madre: **30 días calendario**.

**Inicio de la licencia:**
- Se computa desde la **fecha de nacimiento** del hijo (o desde la fecha que el trabajador elija dentro de los primeros días).
- El trabajador debe comunicar al empleador la fecha probable de parto con **anticipación razonable**.

**Requisitos:**
- Presentar acta o partida de nacimiento del hijo.
- Tener vínculo laboral vigente al momento del nacimiento.
- Aplica a todos los trabajadores del sector privado, independientemente del tipo de contrato.

**Naturaleza económica:**
- La licencia es **con goce de remuneración** íntegra (pagada por el empleador).
- Los días de licencia se consideran como días efectivamente laborados para todos los efectos legales (CTS, vacaciones, gratificaciones).

**Sanción por incumplimiento:**
- El empleador que niegue o reduzca la licencia puede ser sancionado por SUNAFIL.
- El trabajador puede denunciar ante la Autoridad Administrativa de Trabajo.

**En Harmoni:** Asistencia → Papeletas → Tipo: Licencia de paternidad → adjuntar acta de nacimiento → aprobación automática → reflejo en planilla.
''',
    },

    {
        'titulo': 'Hora de Lactancia Materna — Ley 27240',
        'categoria': 'ley_laboral',
        'prioridad': 3,
        'tags': 'lactancia, hora, ley 27240, madre, 1 año, permiso diario, remunerada',
        'contenido': '''\
**Ley 27240 (modificada por Ley 28731) — Hora de Lactancia Materna:**

**Derecho:**
- La madre trabajadora tiene derecho a **1 hora diaria** de permiso por lactancia materna.
- El permiso se otorga hasta que el hijo cumpla **1 año de edad**.
- Es un permiso **remunerado** — no se descuenta de la remuneración ni de las vacaciones.

**Modalidad de uso:**
- La hora de lactancia puede utilizarse:
  - Al **inicio** de la jornada (ingreso 1 hora después).
  - Al **final** de la jornada (salida 1 hora antes).
  - **Fraccionada** en dos periodos de 30 minutos (al inicio y al final, o en otro momento de la jornada).
- La elección corresponde a la **madre trabajadora**, previo acuerdo con el empleador.

**Parto múltiple:**
- En caso de parto múltiple, la hora de lactancia se incrementa en **1 hora adicional** por cada hijo.
- Ejemplo: gemelos = 2 horas diarias de permiso por lactancia.

**No es compensable:**
- La hora de lactancia no puede ser compensada con pago adicional.
- El empleador no puede sustituir el permiso por un incremento remunerativo.
- Tampoco se puede acumular para gozarla en otro momento.

**Sala de lactancia:**
- Empresas con **20 o más trabajadoras en edad fértil** deben implementar una sala de lactancia (Ley 29896).
- La sala debe contar con condiciones mínimas de privacidad, higiene y refrigeración.

**En Harmoni:** Asistencia → configurar el horario de la trabajadora con permiso de lactancia → el sistema ajusta automáticamente la jornada y no marca tardanza ni salida anticipada.
''',
    },

    # ══════════════════════════════════════════════════════════════
    # PLANILLA Y OBLIGACIONES TRIBUTARIAS
    # ══════════════════════════════════════════════════════════════
    {
        'titulo': 'Boleta de Pago — Contenido Obligatorio (DS 001-98-TR)',
        'categoria': 'planilla',
        'prioridad': 1,
        'tags': 'boleta pago, contenido obligatorio, ds 001-98-tr, remuneración, descuentos, firma',
        'contenido': '''\
**DS 001-98-TR, Art. 18-19 — Boleta de Pago:**

**Obligación del empleador:**
- Entregar la boleta de pago al trabajador al momento del pago de la remuneración (dentro del tercer día hábil siguiente).
- La boleta puede ser física o **digital** (con firma digital o constancia electrónica de recepción).

**Contenido mínimo obligatorio:**
1. **Datos del empleador**: razón social, RUC, dirección.
2. **Datos del trabajador**: nombre completo, DNI, cargo, fecha de ingreso, régimen pensionario (AFP/ONP).
3. **Periodo de pago**: mes/quincena/semana y fechas de inicio y fin.
4. **Ingresos**:
   - Remuneración básica.
   - Asignación familiar (si aplica).
   - Horas extra (detalle de horas y porcentaje).
   - Bonificaciones y comisiones.
   - Otros ingresos (movilidad, alimentación, etc.).
5. **Descuentos**:
   - AFP/ONP (aporte obligatorio, comisión, prima de seguro).
   - Impuesto a la Renta 5ta categoría.
   - Préstamos y adelantos.
   - Otros descuentos autorizados.
6. **Aportes del empleador** (informativos): EsSalud (9%), SCTR si aplica.
7. **Neto a pagar**: total ingresos menos total descuentos.
8. **Firma o huella del trabajador** (en boleta física) o constancia de recepción digital.

**Conservación:**
- El empleador debe conservar las boletas por un **mínimo de 5 años** después del cese del trabajador.
- Ante SUNAFIL, la falta de boletas se presume a favor del trabajador.

**En Harmoni:** Nóminas → Boletas → seleccionar periodo → Generar PDF individual o masivo → enviar por email o descargar.
''',
    },

    {
        'titulo': 'PLAME — Declaración Mensual SUNAT',
        'categoria': 'planilla',
        'prioridad': 1,
        'tags': 'plame, sunat, pdt, declaración mensual, planilla electrónica, aportes, retenciones',
        'contenido': '''\
**PLAME — Planilla Mensual de Pagos (SUNAT):**

**¿Qué es?**
- El PLAME es el componente de la Planilla Electrónica donde el empleador declara mensualmente las remuneraciones, aportes y retenciones de sus trabajadores ante SUNAT.
- Es obligatorio para todos los empleadores con trabajadores dependientes.

**¿Qué se declara en el PLAME?**
1. **Remuneraciones** pagadas en el periodo.
2. **Aportes del empleador**: EsSalud (9%), EsSalud Vida, SCTR.
3. **Retenciones al trabajador**: AFP/ONP, IR 5ta categoría.
4. **Días laborados y no laborados** (subsidiados, faltas, etc.).
5. **Conceptos remunerativos y no remunerativos** detallados.

**Plazos de declaración y pago:**
- Se presenta mensualmente según el **cronograma SUNAT** (basado en el último dígito del RUC).
- Generalmente entre el **10 y 20 del mes siguiente** al periodo declarado.
- La declaración y el pago se realizan simultáneamente.

**Componentes de la Planilla Electrónica:**
- **T-Registro**: registro de trabajadores, pensionistas, prestadores de servicios.
- **PLAME**: declaración mensual de pagos (remuneraciones, aportes, retenciones).

**Multas por incumplimiento:**
- No presentar PLAME: infracción tributaria con multa de 1 UIT (S/ 5,500 en 2026).
- Presentar con datos incorrectos: multa del 50% del tributo omitido.
- No pagar aportes/retenciones: intereses moratorios y posible cobranza coactiva.

**En Harmoni:** Nóminas → Exportaciones → PLAME → seleccionar periodo → generar archivo .rem y .jor para carga en el sistema SUNAT.
''',
    },

    {
        'titulo': 'T-Registro — Registro de Trabajadores SUNAT',
        'categoria': 'planilla',
        'prioridad': 2,
        'tags': 't-registro, sunat, alta, baja, modificación, trabajador, 15 días, planilla electrónica',
        'contenido': '''\
**T-Registro — Registro de Información Laboral (SUNAT):**

**¿Qué es?**
- El T-Registro es el componente de la Planilla Electrónica donde se registran los datos de los trabajadores, pensionistas, prestadores de servicios, personal de formación (practicantes) y personal de terceros.
- Es obligatorio para todos los empleadores del sector privado.

**Plazos de registro:**
- **Alta**: dentro de los **15 días calendario** siguientes al inicio de la prestación de servicios (primer día de trabajo).
- **Baja**: dentro de las **24 horas** siguientes al término de la relación laboral.
- **Modificaciones**: dentro de los **5 días hábiles** siguientes al evento (cambio de remuneración, cargo, régimen pensionario, etc.).

**Datos que se registran:**
1. Datos del trabajador: DNI, nombre, fecha de nacimiento, dirección.
2. Datos laborales: fecha de ingreso, tipo de contrato, régimen laboral, ocupación.
3. Datos remunerativos: remuneración mensual, periodicidad de pago.
4. Régimen pensionario: AFP (cuál), ONP, o sin régimen.
5. Régimen de salud: EsSalud o EPS.
6. Situación especial: discapacidad, sindicalización, etc.

**Sanciones por incumplimiento:**
- No registrar trabajadores: infracción **muy grave** ante SUNAFIL.
- Multa: desde 0.5 UIT hasta 50 UIT según número de trabajadores afectados.
- El trabajador no registrado puede demandar laboralmente la existencia de vínculo laboral.

**En Harmoni:** Personal → Nuevo empleado → al guardar, se genera un archivo de exportación compatible con T-Registro → el usuario lo carga en el portal SUNAT.
''',
    },

    {
        'titulo': 'Remuneración Mínima Vital — RMV 2025 S/ 1,130 (DS 006-2024-TR)',
        'categoria': 'planilla',
        'prioridad': 1,
        'tags': 'rmv, remuneración mínima vital, sueldo mínimo, 1130, ds 006-2024-tr, 2025',
        'contenido': '''\
**Remuneración Mínima Vital (RMV) — DS 006-2024-TR:**

**Monto vigente:**
- **S/ 1,130 mensuales** desde el **1 de enero de 2025**.
- Incremento anterior: de S/ 1,025 a S/ 1,130 (aumento de S/ 105).

**¿A quién aplica?**
- A todos los trabajadores del **régimen laboral de la actividad privada** que laboran una jornada mínima de 4 horas diarias o 24 horas semanales.
- Trabajadores con jornada menor a 4 horas diarias: remuneración proporcional (part-time).
- No aplica a trabajadores del hogar (tienen su propia regulación) ni a regímenes especiales (agrario, MYPE).

**Conceptos vinculados a la RMV:**
- **Asignación familiar**: 10% de RMV = S/ 113.00.
- **Jornada nocturna mínima**: RMV + 35% = S/ 1,525.50.
- **Gratificación mínima**: igual a 1 RMV = S/ 1,130 por semestre completo.
- **CTS semestral mínima**: 1/6 de RMV × 6 meses = S/ 1,130 ÷ 6 × 6 = S/ 1,130 máximo (aproximado).

**Regímenes especiales:**
- **Microempresa** (Ley MYPE): RMV completa, sin CTS ni gratificaciones.
- **Pequeña empresa**: RMV completa, CTS 15 días/año, gratificaciones de medio sueldo.
- **Régimen agrario**: RMV con inclusión proporcional de gratificaciones y CTS en la remuneración diaria.

**Actualización en Harmoni:**
- Configuración → Parámetros Legales → RMV → actualizar el monto cuando cambie por decreto supremo.
- El cambio de RMV recalcula automáticamente: asignación familiar, mínimo de jornada nocturna y validaciones de sueldo mínimo.
''',
    },

    {
        'titulo': 'Jornada Nocturna — Recargo 35% Mínimo (DL 854)',
        'categoria': 'ley_laboral',
        'prioridad': 2,
        'tags': 'jornada nocturna, recargo 35%, horario nocturno, 10pm, 6am, dl 854, turno noche',
        'contenido': '''\
**D.Leg. 854 — Jornada Nocturna:**

**Definición:**
- Se considera **jornada nocturna** el trabajo realizado entre las **10:00 p.m. y las 6:00 a.m.** del día siguiente.

**Recargo mínimo:**
- La remuneración del trabajador nocturno no puede ser menor a la **RMV vigente más un 35%**.
- Con RMV 2025 de S/ 1,130: sueldo mínimo nocturno = **S/ 1,525.50**.
- Si el trabajador ya percibe un sueldo superior al mínimo nocturno, **no se paga recargo adicional** (el recargo se aplica solo para garantizar el piso mínimo).

**Aclaraciones importantes:**
- El recargo del 35% aplica cuando la jornada nocturna es **habitual** (turno fijo de noche).
- Para trabajadores rotativos que eventualmente cubren turno noche, se aplica el recargo proporcionalmente a las horas nocturnas laboradas.
- No se debe confundir con el recargo por **horas extra**: las HE nocturnas se calculan sobre la remuneración con recargo nocturno.

**Ejemplo de cálculo combinado (HE nocturnas):**
- Sueldo base con recargo nocturno: S/ 2,000.
- Valor hora: S/ 2,000 ÷ 30 ÷ 8 = S/ 8.33.
- 2 primeras HE nocturnas: S/ 8.33 × 1.25 = S/ 10.42/hora.
- Desde 3.ª HE nocturna: S/ 8.33 × 1.35 = S/ 11.25/hora.

**Restricciones:**
- Menores de edad no pueden trabajar en jornada nocturna (Código del Niño y Adolescente).
- Mujeres gestantes: no pueden ser asignadas a turno nocturno si existe certificado médico que lo contraindique.

**En Harmoni:** Personal → ficha del empleado → Turno: Nocturno → el sistema ajusta automáticamente la validación de sueldo mínimo y el cálculo de HE.
''',
    },

    # ══════════════════════════════════════════════════════════════
    # ASISTENCIA Y OPERACIONES
    # ══════════════════════════════════════════════════════════════
    {
        'titulo': 'Régimen Acumulativo Atípico — Art. 4 DS 007-2002-TR',
        'categoria': 'asistencia',
        'prioridad': 1,
        'tags': 'régimen atípico, acumulativo, 14x7, 21x7, 10x4, ds 007-2002-tr, minería, jornada especial',
        'contenido': '''\
**DS 007-2002-TR, Art. 4 — Jornadas Atípicas o Acumulativas:**

**¿Qué es?**
- Son jornadas de trabajo que acumulan horas en periodos mayores a una semana, compensándolas con días de descanso.
- Comunes en minería, petróleo, construcción remota y proyectos en zonas alejadas.

**Ciclos más frecuentes:**
- **14×7**: 14 días de trabajo consecutivo + 7 días de descanso.
- **21×7**: 21 días de trabajo + 7 días de descanso.
- **10×4**: 10 días de trabajo + 4 días de descanso.
- **20×10**: 20 días de trabajo + 10 días de descanso.
- **4×3**: 4 días de trabajo + 3 días de descanso (para guardias).

**Requisitos legales:**
- El promedio de horas trabajadas en el ciclo completo **no debe exceder 8 horas diarias ni 48 horas semanales**.
- Ejemplo 14×7: 14 días × 12 horas ÷ 21 días del ciclo = 8 horas promedio diario (cumple).
- Las horas que exceden el promedio se compensan con los días de descanso del ciclo.

**Criterios del Tribunal Constitucional (STC 4635-2004-AA):**
- Las jornadas atípicas son constitucionales siempre que se respete el promedio de 8 horas diarias/48 semanales.
- Se debe garantizar condiciones de seguridad y salud en el trabajo.
- Alimentación y alojamiento a cargo del empleador cuando el personal labora en zonas alejadas.

**En Harmoni:** Personal → Configuración de Turno → Tipo: Régimen atípico → definir ciclo (días trabajo × días descanso) → asignar a empleados → el módulo Asistencia controla automáticamente.
''',
    },

    {
        'titulo': 'Trabajo Remoto y Teletrabajo — Ley 31572',
        'categoria': 'ley_laboral',
        'prioridad': 2,
        'tags': 'teletrabajo, trabajo remoto, ley 31572, domicilio, compensación, desconexión digital',
        'contenido': '''\
**Ley 31572 — Ley de Teletrabajo (vigente desde 2023):**

**Definición:**
- El teletrabajo es la prestación de servicios subordinada, sin presencia física en el centro de trabajo, utilizando **tecnologías de la información y comunicación (TIC)**.
- Puede ser total (100% remoto) o parcial (mixto/híbrido).

**Modalidades:**
- **Teletrabajo total**: el trabajador labora exclusivamente desde su domicilio o lugar elegido.
- **Teletrabajo parcial o híbrido**: combina días presenciales y remotos.
- El acuerdo de teletrabajo debe constar por **escrito** (contrato o adenda).

**Obligaciones del empleador:**
1. **Compensar gastos**: proporcionar o reembolsar equipos, internet, energía eléctrica y otros gastos vinculados.
2. **Capacitación**: instruir al teletrabajador en el uso de herramientas digitales y medidas de seguridad.
3. **Seguridad y salud**: evaluar las condiciones ergonómicas del puesto remoto.
4. **Derecho a la desconexión digital**: respetar el horario de trabajo, no contactar fuera de jornada salvo emergencias.

**Derechos del teletrabajador:**
- Misma remuneración y beneficios que el personal presencial (igualdad de trato).
- Derecho a la **reversibilidad**: el trabajador puede solicitar volver a la modalidad presencial (y viceversa, según acuerdo).
- Protección de datos personales y privacidad.
- Derecho a la desconexión digital fuera del horario laboral.

**Control de asistencia:**
- El empleador puede implementar mecanismos de control digital (registro de conexión/desconexión).
- No se puede usar software invasivo de vigilancia (capturas de pantalla constantes, grabación de cámara sin consentimiento).

**En Harmoni:** Personal → ficha del empleado → Modalidad: Teletrabajo → configurar días remotos/presenciales → Asistencia registra marcaciones digitales (login/logout del sistema).
''',
    },

    {
        'titulo': 'Tolerancia de Tardanza — Política y Práctica Laboral',
        'categoria': 'asistencia',
        'prioridad': 3,
        'tags': 'tolerancia, tardanza, 10 minutos, gracia, retraso, descuento, política interna',
        'contenido': '''\
**Tolerancia de Tardanza — Marco Legal y Práctica:**

**¿Existe una tolerancia legal obligatoria?**
- La ley peruana **no establece** un periodo de tolerancia mínimo obligatorio para tardanzas.
- La tolerancia es una **política interna** del empleador, establecida en el Reglamento Interno de Trabajo (RIT).
- La práctica más común en empresas peruanas es otorgar **10 minutos** de tolerancia.

**Política típica en empresas peruanas:**
- **0 a 10 minutos**: tolerancia sin descuento (gracia).
- **11 a 30 minutos**: se registra como tardanza, descuento proporcional.
- **Más de 30 minutos**: puede considerarse como inasistencia parcial según política interna.
- Tardanzas reiteradas (3 o más en un mes): amonestación escrita progresiva.

**Cálculo del descuento por tardanza:**
- Fórmula: (Sueldo mensual ÷ 30 ÷ jornada en minutos) × minutos de tardanza.
- Ejemplo: Sueldo S/ 3,000, jornada 8 horas, tardanza 25 minutos.
- Descuento = (S/ 3,000 ÷ 30 ÷ 480) × 25 = S/ 0.2083 × 25 = **S/ 5.21**.

**Reglamento Interno de Trabajo (RIT):**
- El empleador con 100+ trabajadores está obligado a tener RIT (DS 039-91-TR).
- El RIT debe especificar: tolerancia, sanciones por tardanza, procedimiento de justificación.
- El RIT debe ser aprobado por la Autoridad Administrativa de Trabajo y comunicado a los trabajadores.

**En Harmoni:** Configuración → Parámetros de Asistencia → Tolerancia de tardanza → definir minutos de gracia → el sistema aplica automáticamente el descuento o la tolerancia al procesar marcaciones.
''',
    },

    {
        'titulo': 'Descanso Semanal Obligatorio — 24 Horas Consecutivas (DL 713)',
        'categoria': 'ley_laboral',
        'prioridad': 2,
        'tags': 'descanso semanal, dso, domingo, 24 horas, obligatorio, dl 713, día libre',
        'contenido': '''\
**D.Leg. 713, Art. 1-3 — Descanso Semanal Obligatorio (DSO):**

**Marco legal:**
- Todo trabajador tiene derecho a un descanso semanal mínimo de **24 horas consecutivas**.
- Preferentemente se otorga en **domingo**, pero puede ser otro día de la semana según acuerdo o naturaleza de la actividad.
- El DSO es **remunerado** — el trabajador percibe su remuneración ordinaria por ese día.

**Trabajo en día de descanso semanal:**
- Si el trabajador labora en su DSO **sin descanso sustitutorio**: tiene derecho al pago con sobretasa del **100%** (remuneración ordinaria + sobretasa).
- Si se otorga **descanso sustitutorio** en otro día de la semana: no se paga sobretasa, solo se traslada el descanso.

**Requisitos para gozar del pago del DSO:**
- Haber **laborado todos los días hábiles** de la semana (lunes a sábado en jornada de 6 días, o lunes a viernes en jornada de 5 días).
- Las faltas injustificadas en la semana pueden generar la **pérdida proporcional** del pago del descanso semanal.

**Descanso en regímenes atípicos:**
- En jornadas 14×7, 21×7, etc., los días de descanso del ciclo cumplen la función del DSO.
- Se debe garantizar que el promedio de descanso semanal sea al menos de 24 horas.

**En Harmoni:** el día de descanso semanal se configura por turno (Personal → Turnos → DSO). El módulo Asistencia controla que el trabajador no labore más de 6 días consecutivos sin descanso.
''',
    },

    # ══════════════════════════════════════════════════════════════
    # GUÍAS OPERATIVAS DE HARMONI ERP
    # ══════════════════════════════════════════════════════════════
    {
        'titulo': 'Cómo Generar una Planilla en Harmoni — Paso a Paso',
        'categoria': 'proceso',
        'prioridad': 1,
        'tags': 'planilla, nómina, generar, paso a paso, cálculo, cierre, proceso, guía',
        'contenido': '''\
**Guía: Generar la Planilla Mensual en Harmoni**

**Prerrequisitos:**
- Asistencia del periodo cerrada y validada (módulo Asistencia → Cierre de periodo).
- Novedades registradas: permisos, licencias, faltas, horas extra.
- Préstamos y adelantos al día (módulo Préstamos).
- Conceptos remunerativos configurados (módulo Nóminas → Conceptos).

**Proceso paso a paso:**

**1. Verificar asistencia (Asistencia → Resumen del Periodo):**
- Revisar marcaciones importadas del biométrico o registradas manualmente.
- Confirmar HE calculadas correctamente (STAFF → banco de horas, RCO → pago directo).
- Validar faltas, tardanzas y permisos justificados.

**2. Abrir periodo de nómina (Nóminas → Periodos → Nuevo Periodo):**
- Seleccionar mes y año.
- El sistema crea el periodo con fechas de inicio y fin automáticas (21 del mes anterior al 20 del mes actual).

**3. Calcular planilla (Nóminas → Calcular):**
- Seleccionar el periodo abierto.
- El sistema calcula para cada empleado: ingresos (básico + asignación familiar + HE + bonos), descuentos (AFP/ONP, IR5, préstamos, faltas), aportes del empleador (EsSalud, SCTR).
- Revisar el log de cálculo para detectar errores o alertas.

**4. Revisar y aprobar (Nóminas → Registro de Nómina):**
- Verificar línea por línea los montos calculados.
- Corregir manualmente si hay discrepancias (agregar conceptos especiales, bonos, descuentos).

**5. Cerrar periodo (Nóminas → Cerrar Periodo):**
- Al cerrar, los registros quedan bloqueados (no editables).
- Generar boletas de pago PDF para distribución.

**6. Exportar PLAME (Nóminas → Exportaciones → PLAME):**
- Generar archivos .rem y .jor para carga en el sistema SUNAT.
''',
    },

    {
        'titulo': 'Cómo Aprobar Vacaciones en Harmoni — Flujo Completo',
        'categoria': 'proceso',
        'prioridad': 1,
        'tags': 'vacaciones, aprobar, solicitud, flujo, aprobación, jefe, rrhh, guía',
        'contenido': '''\
**Guía: Flujo de Aprobación de Vacaciones en Harmoni**

**Paso 1 — Solicitud del empleado:**
- El empleado ingresa al **Portal del Empleado** o al módulo **Vacaciones → Nueva Solicitud**.
- Selecciona: fecha de inicio, fecha de fin, días solicitados.
- Opcionalmente marca "Incluir venta de vacaciones" (máx. 15 días).
- El sistema valida automáticamente:
  - Saldo vacacional disponible (debe tener días suficientes).
  - No superposición con otras solicitudes aprobadas.
  - No conflicto con periodos de cierre o fechas restringidas.
- Envía la solicitud al jefe directo.

**Paso 2 — Aprobación del jefe directo:**
- El jefe recibe notificación (email y campana en Harmoni).
- Revisa la solicitud en **Vacaciones → Solicitudes Pendientes**.
- Puede: **Aprobar**, **Rechazar** (con motivo) o **Solicitar cambio de fechas**.
- Si aprueba, la solicitud pasa a RRHH para validación final.

**Paso 3 — Validación de RRHH:**
- RRHH revisa que todo esté conforme (saldo correcto, no conflictos legales).
- **Aprueba definitivamente** o devuelve al jefe con observaciones.
- Al aprobar, el sistema:
  - Descuenta los días del saldo vacacional.
  - Registra las fechas en el calendario del área.
  - Marca los días como "vacaciones" en el módulo Asistencia.
  - Genera la boleta de goce vacacional (si está configurado).

**Paso 4 — Notificación al empleado:**
- El empleado recibe confirmación por email y en el Portal.
- Puede descargar su constancia de vacaciones aprobadas.

**Cancelación:**
- El empleado puede cancelar antes de la fecha de inicio (requiere aprobación del jefe).
- Si ya inició el goce, la interrupción requiere motivo justificado y aprobación de RRHH.
''',
    },

    {
        'titulo': 'Cómo Importar Asistencia desde Excel o Biométrico',
        'categoria': 'proceso',
        'prioridad': 1,
        'tags': 'importar, asistencia, excel, biométrico, marcaciones, reloj, carga masiva, guía',
        'contenido': '''\
**Guía: Importar Asistencia en Harmoni**

**Opción 1 — Importación desde Reloj Biométrico:**

1. **Configurar el reloj** (una sola vez):
   - Asistencia → Configuración → Relojes Biométricos → Nuevo Reloj.
   - Ingresar: nombre, IP, puerto, marca/modelo, ubicación.
   - Probar conexión para verificar comunicación.

2. **Sincronizar marcaciones:**
   - Asistencia → Importar → Desde Biométrico.
   - Seleccionar reloj y rango de fechas.
   - El sistema descarga las marcaciones y las asocia automáticamente a los empleados por su código biométrico.
   - Revisar el log de importación: marcaciones exitosas, no identificadas y duplicadas.

**Opción 2 — Importación desde Excel:**

1. **Descargar plantilla:**
   - Asistencia → Importar → Desde Excel → Descargar Plantilla.
   - La plantilla incluye columnas: código empleado, fecha, hora entrada, hora salida.

2. **Completar la plantilla:**
   - Llenar con los datos de marcaciones del periodo.
   - Formatos: fecha (DD/MM/AAAA), hora (HH:MM en 24h).

3. **Cargar el archivo:**
   - Asistencia → Importar → Desde Excel → Seleccionar archivo.
   - El sistema con IA realiza **mapeo inteligente de columnas** (si la plantilla tiene columnas con nombres diferentes, la IA las identifica).
   - Vista previa de datos antes de confirmar.
   - Confirmar importación.

4. **Validación post-importación:**
   - Revisar el resumen: marcaciones importadas, errores, empleados no encontrados.
   - Corregir marcaciones inconsistentes (entrada sin salida, horarios imposibles).

**Consejo:** importar asistencia **diariamente o semanalmente** para detectar inconsistencias a tiempo, no esperar al cierre mensual.
''',
    },

    {
        'titulo': 'Cómo Generar Boletas de Pago PDF — Individual y Masivo',
        'categoria': 'proceso',
        'prioridad': 1,
        'tags': 'boleta, pdf, generar, individual, masivo, imprimir, email, reportlab, guía',
        'contenido': '''\
**Guía: Generar Boletas de Pago PDF en Harmoni**

**Prerrequisito:**
- El periodo de nómina debe estar **calculado** (puede estar abierto o cerrado).
- Las líneas de nómina deben tener datos (ingresos, descuentos, neto).

**Generación Individual:**

1. Ir a **Nóminas → Registro de Nómina** → seleccionar periodo.
2. Ubicar al empleado en la lista.
3. Clic en el botón **"Ver Boleta PDF"** (ícono de PDF).
4. Se abre la boleta en nueva pestaña o se descarga directamente.
5. La boleta incluye: datos del empleador, datos del trabajador, periodo, detalle de ingresos, detalle de descuentos, aportes del empleador (informativo), neto a pagar.

**Generación Masiva:**

1. Ir a **Nóminas → Boletas → Generar Masivo**.
2. Seleccionar periodo de nómina.
3. Filtrar por: área, tipo de empleado (STAFF/RCO), o todos.
4. Clic en **"Generar Boletas PDF"**.
5. El sistema genera un archivo ZIP con todas las boletas individuales.
6. Cada boleta se nombra: `boleta_{periodo}_{codigo_empleado}.pdf`.

**Envío por Email:**

1. En la vista de generación masiva, marcar **"Enviar por email"**.
2. El sistema envía cada boleta al correo registrado del empleado.
3. Se muestra un log de envío: exitosos, fallidos (sin email registrado), rebotados.

**Generación desde el Chat IA:**
- El asistente IA puede generar boletas individuales. Pedir: "Genera la boleta de [nombre del empleado] del periodo [mes/año]".
- La IA busca al empleado, localiza el registro de nómina y genera el PDF.

**Personalización:**
- El formato de la boleta se puede personalizar en Nóminas → Configuración → Formato de Boleta.
- Logo de la empresa, colores, campos adicionales.
''',
    },

    {
        'titulo': 'Cómo Configurar Regímenes de Turno en Harmoni',
        'categoria': 'proceso',
        'prioridad': 2,
        'tags': 'turno, régimen, configurar, horario, rotación, atípico, nocturno, diurno, guía',
        'contenido': '''\
**Guía: Configurar Regímenes de Turno en Harmoni**

**¿Qué es un régimen de turno?**
- Es la configuración del horario de trabajo que se asigna a los empleados: días laborales, horario de entrada/salida, tipo de jornada y ciclo de rotación.

**Acceso:**
- Personal → Configuración → Turnos (o Configuración → Regímenes de Turno).

**Crear un turno estándar (diurno):**
1. Clic en **"Nuevo Turno"**.
2. Completar:
   - Nombre: ej. "Oficina Diurno L-V".
   - Tipo: Estándar.
   - Hora entrada: 08:00.
   - Hora salida: 17:00.
   - Refrigerio: 45 minutos (12:00–12:45).
   - Días laborales: Lunes a Viernes.
   - DSO (día de descanso semanal): Domingo.
   - Tolerancia de entrada: 10 minutos.

**Crear un turno nocturno:**
1. Mismo proceso, configurando:
   - Hora entrada: 22:00.
   - Hora salida: 06:00 (+1 día).
   - Marcar como "Turno Nocturno" → el sistema valida que la remuneración cumpla con el mínimo nocturno (RMV + 35%).

**Crear un régimen atípico (ej. 14×7):**
1. Tipo: Atípico/Acumulativo.
2. Días de trabajo: 14.
3. Días de descanso: 7.
4. Hora entrada: 07:00.
5. Hora salida: 19:00 (12 horas diarias).
6. El sistema valida que el promedio no exceda 48 horas semanales.

**Asignar turno a empleados:**
- Personal → ficha del empleado → pestaña Turno → seleccionar régimen.
- Se puede asignar masivamente: Personal → Asignación Masiva de Turno → seleccionar empleados y turno.

**Rotación automática:**
- Para regímenes con rotación (día/noche), configurar el ciclo de rotación y el sistema asigna automáticamente el turno correspondiente por semana/quincena.
''',
    },

    {
        'titulo': 'Portal del Colaborador — Funcionalidades de Autoservicio',
        'categoria': 'proceso',
        'prioridad': 2,
        'tags': 'portal, colaborador, empleado, autoservicio, mis datos, solicitudes, boletas, saldo',
        'contenido': '''\
**Portal del Colaborador en Harmoni — Guía de Funcionalidades**

**¿Qué es?**
- Es el módulo de **autoservicio** donde los empleados pueden consultar su información, realizar solicitudes y descargar documentos sin depender de RRHH.
- Acceso: URL de la empresa → Login con credenciales personales.

**Funcionalidades disponibles:**

**1. Mis Datos Personales:**
- Consulta de datos: nombre, DNI, cargo, área, fecha de ingreso, tipo de contrato.
- Actualización de datos de contacto: teléfono, email, dirección (sujeto a aprobación de RRHH).
- Foto de perfil.

**2. Mis Boletas de Pago:**
- Consulta y descarga de boletas de pago en PDF por periodo.
- Historial completo de boletas desde el ingreso.
- Firma electrónica de conformidad de la boleta.

**3. Mis Vacaciones:**
- Saldo vacacional actualizado (días generados, gozados, disponibles).
- Solicitar vacaciones (flujo de aprobación jefe → RRHH).
- Historial de vacaciones gozadas y solicitudes.

**4. Mis Permisos y Licencias:**
- Solicitar permisos (médico, personal, capacitación, etc.).
- Ver estado de solicitudes (pendiente, aprobado, rechazado).
- Adjuntar documentos justificatorios.

**5. Mi Asistencia:**
- Consulta de marcaciones del mes.
- Banco de horas (STAFF): saldo acumulado, compensaciones.
- Reporte de tardanzas y faltas.

**6. Mis Préstamos y Adelantos:**
- Saldo de préstamos activos, cuotas pagadas y pendientes.
- Solicitar adelanto de sueldo (si la política lo permite).

**7. Mis Documentos:**
- Descargar: constancia de trabajo, certificados de capacitación, contratos.
- Cargar documentos: certificados de estudio, declaraciones juradas.

**8. Asistente IA:**
- Chat integrado para consultas sobre beneficios, ley laboral, procesos internos.
- Disponible en la esquina inferior derecha del portal.
''',
    },

    # ══════════════════════════════════════════════════════════════
    # ARTÍCULOS ADICIONALES DE LEY LABORAL
    # ══════════════════════════════════════════════════════════════
    {
        'titulo': 'Vacaciones No Gozadas — Triple Vacacional (DL 713, Art. 23)',
        'categoria': 'vacaciones',
        'prioridad': 2,
        'tags': 'triple vacacional, vacaciones no gozadas, indemnización, dl 713, artículo 23',
        'contenido': '''\
**D.Leg. 713, Art. 23 — Indemnización por Vacaciones No Gozadas (Triple Vacacional):**

**¿Cuándo se genera?**
- Cuando el trabajador no goza de sus vacaciones dentro del **año siguiente** a la fecha en que adquirió el derecho (récord vacacional).
- Ejemplo: si el récord vacacional se generó el 1 de marzo de 2025, debe gozar sus vacaciones antes del 28 de febrero de 2026.

**Composición de la "triple vacacional":**
1. **Una remuneración** por el trabajo realizado (ya pagada mes a mes).
2. **Una remuneración** por el descanso vacacional adquirido y no gozado.
3. **Una indemnización** equivalente a una remuneración por no haber disfrutado del descanso.
- Total: el trabajador percibe el equivalente a **3 remuneraciones** por el periodo vacacional no gozado.

**Cálculo:**
- Remuneración computable: básico + asignación familiar + promedio de comisiones/HE de los últimos 12 meses.
- Triple vacacional = Remuneración computable × 3 (la primera ya fue pagada, así que se paga 2 adicionales).

**Aspectos importantes:**
- La triple vacacional **no prescribe** mientras dure la relación laboral. Al cese, prescribe a los **4 años** desde el cese.
- El empleador puede ser multado por SUNAFIL por no otorgar vacaciones oportunamente.
- La acumulación de vacaciones no gozadas es una **infracción grave** en materia laboral.

**Prevención en Harmoni:**
- El módulo Vacaciones genera **alertas automáticas** cuando un empleado tiene vacaciones próximas a vencer (90, 60 y 30 días antes).
- Analytics → Alertas RRHH muestra el listado de empleados con riesgo de triple vacacional.
''',
    },

    {
        'titulo': 'Participación en Utilidades — DL 892',
        'categoria': 'beneficios',
        'prioridad': 2,
        'tags': 'utilidades, participación, dl 892, reparto, porcentaje, 50% días, 50% remuneración',
        'contenido': '''\
**D.Leg. 892 — Participación en Utilidades:**

**¿Quiénes están obligados?**
- Empresas privadas que generan **rentas de tercera categoría** con más de **20 trabajadores**.
- Se calcula sobre la **renta neta imponible** del ejercicio fiscal (antes del IR).

**Porcentajes según actividad económica:**
- Empresas pesqueras: **10%**.
- Empresas de telecomunicaciones: **10%**.
- Empresas industriales: **10%**.
- Empresas mineras: **8%**.
- Empresas de comercio y restaurantes: **8%**.
- Empresas de otras actividades: **5%**.

**Distribución del monto (dos criterios):**
- **50%** en función de los **días efectivamente laborados** por cada trabajador.
- **50%** en proporción a las **remuneraciones percibidas** por cada trabajador.
- Tope individual: 18 remuneraciones mensuales del trabajador.

**Plazo de pago:**
- Dentro de los **30 días naturales** siguientes al vencimiento del plazo para la presentación de la DJ Anual del IR (generalmente entre marzo y abril).

**Trabajadores con derecho:**
- Todos los que hayan laborado durante el ejercicio fiscal (incluso si cesaron antes del reparto).
- Las utilidades de trabajadores cesados no reclamadas prescriben a los **4 años**.

**En Harmoni:** Nóminas → Utilidades → Cargar renta neta del ejercicio → el sistema calcula automáticamente la distribución por empleado según los dos criterios.
''',
    },
]


class Command(BaseCommand):
    help = 'Carga la base de conocimiento inicial para Harmoni AI (ley laboral peruana, procesos, FAQ)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Actualiza artículos existentes aunque ya existan.'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra qué se cargaría sin insertar en BD.'
        )

    def handle(self, *args, **options):
        force   = options['force']
        dry_run = options['dry_run']

        created = updated = skipped = 0

        for art in ARTICLES:
            titulo = art['titulo']

            if dry_run:
                self.stdout.write(f'  [?] {titulo}')
                continue

            existing = KnowledgeArticle.objects.filter(titulo=titulo).first()

            if existing:
                if force:
                    for field, val in art.items():
                        setattr(existing, field, val)
                    existing.save()
                    updated += 1
                    self.stdout.write(f'  [U] Actualizado: {titulo}')
                else:
                    skipped += 1
                    self.stdout.write(f'  [-] Existe (omitido): {titulo}')
            else:
                KnowledgeArticle.objects.create(**art)
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  [+] Creado: {titulo}'))

        if not dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(
                f'Base de conocimiento: {created} creados, {updated} actualizados, {skipped} omitidos.'
            ))
            self.stdout.write(
                f'Total en BD: {KnowledgeArticle.objects.count()} artículos activos.'
            )
