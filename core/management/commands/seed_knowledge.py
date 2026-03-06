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
- La RMV vigente en Perú es **S/ 1,025** (desde mayo 2022).
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
- Equivale al **10% de la RMV** vigente = S/ 102.50 (con RMV de S/ 1,025).
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
