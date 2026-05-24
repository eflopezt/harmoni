"""
RAG normativa peruana — base inicial.

Versión 1 (esta jornada): conocimiento base como diccionario estructurado
con búsqueda por keywords + scoring simple.

Versión 2 (futuro): chunks + embeddings pgvector + búsqueda semántica.

Cada entrada tiene:
- titulo, base_legal, descripcion (markdown)
- keywords (lista para matching)
- tags (categorías)
"""
import re
from decimal import Decimal


NORMATIVA = [
    # ─── Gratificación ───────────────────────────────────────────
    {
        'titulo':      'Gratificación legal — Julio y Diciembre',
        'base_legal':  'Ley 27735 + DS 005-2002-TR',
        'tags':        ['gratificacion', 'bonificacion'],
        'keywords':    ['gratificación', 'gratificacion', 'gratif', 'julio', 'diciembre',
                        'aguinaldo', 'medio sueldo', 'sueldo extra'],
        'descripcion': """\
**Gratificación legal** (Ley 27735):
- 2 pagos al año: 1 en julio (hasta el 15) y 1 en diciembre (hasta el 15)
- Monto: equivalente a 1 remuneración computable por cada semestre completo (enero-junio para julio, julio-diciembre para diciembre)
- Computable: sueldo básico + asignación familiar + otros conceptos remunerativos regulares
- Trabajadores con menos de 6 meses: proporcional (1/6 por cada mes trabajado completo)

**Bonificación extraordinaria 9%** (Ley 29351 + Ley 30334 — permanente):
- Adicional sobre la gratificación
- 9% si está en ESSALUD regular
- 6.75% si tiene EPS (crédito empleador 25%)
""",
    },

    # ─── CTS ─────────────────────────────────────────────────────
    {
        'titulo':      'CTS — Compensación por Tiempo de Servicios',
        'base_legal':  'D.Leg. 650 + DS 004-97-TR',
        'tags':        ['cts', 'beneficios'],
        'keywords':    ['cts', 'compensación tiempo', 'compensacion tiempo', 'mayo',
                        'noviembre', 'depósito cts', 'deposito cts'],
        'descripcion': """\
**CTS — Compensación por Tiempo de Servicios** (D.Leg. 650):
- 2 depósitos al año: hasta el 15 de mayo (semestre noviembre-abril) y hasta el 15 de noviembre (semestre mayo-octubre)
- Monto: 1 remuneración al año, depositado por mes calendario completo
- Remuneración computable = sueldo + 1/6 de la gratificación de ese semestre
- Cálculo: REM_computable × meses_completos/12 + REM_computable × días/(12×30)
- Se deposita en el banco que el trabajador elige (intangible salvo retiro voluntario hasta el 100%)
- Empresa NO descuenta CTS de la planilla del trabajador
""",
    },

    # ─── EPS ─────────────────────────────────────────────────────
    {
        'titulo':      'EPS — Entidades Prestadoras de Salud',
        'base_legal':  'Ley 26790',
        'tags':        ['eps', 'essalud', 'salud'],
        'keywords':    ['eps', 'essalud', 'salud', 'crédito empleador', 'credito empleador',
                        'rímac', 'pacifico', 'mapfre', 'sanitas'],
        'descripcion': """\
**EPS — Entidades Prestadoras de Salud** (Ley 26790):
- Trabajador puede elegir EPS en lugar de ESSALUD para capa simple (24%)
- ESSALUD sigue cubriendo capa compleja (76%) — empleador sigue aportando 9%
- Empleador obtiene **crédito EPS** = 25% del aporte ESSALUD efectivo
- Resultado neto: ESSALUD efectivo baja de 9% a **6.75%**
- Esto aplica TAMBIÉN a la bonificación extraordinaria de la gratificación: 6.75% en lugar de 9%

**Ejemplo**: trabajador con sueldo S/3000 que tiene EPS:
- ESSALUD que pagaría empleador: 3000 × 9% = 270
- Crédito EPS (25% × 270): 67.50
- ESSALUD efectivo: 270 - 67.50 = 202.50 (= 3000 × 6.75%)
""",
    },

    # ─── AFP / ONP ───────────────────────────────────────────────
    {
        'titulo':      'Sistema Privado de Pensiones (AFP)',
        'base_legal':  'DL 25897 + Resoluciones SBS',
        'tags':        ['afp', 'pension', 'spp'],
        'keywords':    ['afp', 'integra', 'prima', 'habitat', 'profuturo', 'pension',
                        'spp', 'comisión flujo', 'comision flujo', 'prima seguro'],
        'descripcion': """\
**AFP — Sistema Privado de Pensiones** (DL 25897):
3 componentes que se descuentan al trabajador:
- **Aporte obligatorio: 10%** del sueldo bruto (sin tope)
- **Comisión por flujo**: 1.47% (Habitat) a 1.69% (Profuturo) — varía por AFP
- **Prima de seguro**: 1.74% uniforme — aplica HASTA el tope RMA (~S/12,131)

**Tope RMA** (Remuneración Máxima Asegurable):
- Solo aplica para la prima de seguro
- El 10% obligatorio y comisión por flujo NO tienen tope

**Tasas vigentes Q2 2026** (Resolución SBS):
- Habitat:   1.47% comisión / 1.74% seguro
- Integra:   1.55% / 1.74%
- Prima:     1.60% / 1.74%
- Profuturo: 1.69% / 1.74%
""",
    },
    {
        'titulo':      'ONP — Oficina de Normalización Previsional',
        'base_legal':  'DL 19990',
        'tags':        ['onp', 'pension', 'snp'],
        'keywords':    ['onp', 'sistema nacional pensiones', 'snp', '13%'],
        'descripcion': """\
**ONP — Sistema Nacional de Pensiones** (DL 19990):
- Tasa única: **13%** sobre el sueldo bruto
- **Sin tope** (a diferencia del 19% que tenía antes, hoy es 13% sin tope desde 2013)
- Pagado por el trabajador (descontado de su sueldo)
- Acumula años de aporte para jubilación (mínimo 20 años en el sistema)
""",
    },

    # ─── IR 5ta categoría ────────────────────────────────────────
    {
        'titulo':      'Impuesto a la Renta 5ta Categoría',
        'base_legal':  'Art. 53° y 75° TUO LIR + R.S. 010-2006/SUNAT',
        'tags':        ['ir', 'renta', '5ta', 'impuesto'],
        'keywords':    ['ir 5ta', 'ir5ta', 'renta', 'retención', 'retencion', 'impuesto'],
        'descripcion': """\
**IR 5ta Categoría** — Impuesto a la Renta sobre remuneraciones (TUO LIR):

**Escala progresiva 2026** (sobre lo que excede 7 UIT):
| Tramo | UIT | Tasa |
|-------|-----|------|
| Hasta 5 UIT | hasta S/27,500 | 8% |
| 5 a 20 UIT | S/27,501 - S/110,000 | 14% |
| 20 a 35 UIT | S/110,001 - S/192,500 | 17% |
| 35 a 45 UIT | S/192,501 - S/247,500 | 20% |
| Más de 45 UIT | > S/247,500 | 30% |

**UIT 2026: S/ 5,500** (DS 233-2025-EF)
**Deducción anual**: 7 UIT = S/ 38,500

**Método de retención** (SUNAT):
1. Proyectar remuneración anual = (sueldo × meses restantes) + variables percibidas + gratificaciones futuras
2. Restar 7 UIT + EPS trabajador
3. Aplicar escala → impuesto anual proyectado
4. Dividir entre meses restantes (incluyendo el actual) = retención del mes
""",
    },

    # ─── Asignación familiar ─────────────────────────────────────
    {
        'titulo':      'Asignación Familiar',
        'base_legal':  'Ley 25129',
        'tags':        ['asignacion_familiar', 'familia'],
        'keywords':    ['asignación familiar', 'asignacion familiar', 'hijos', 'familiar',
                        '10% rmv', 'asig fam'],
        'descripcion': """\
**Asignación Familiar** (Ley 25129):
- **Monto: 10% de la RMV** = S/ 113.00 (2026, RMV S/1,130)
- Condición: trabajador con al menos un **hijo menor de 18 años** (o estudiante hasta 24)
- Aplica a trabajadores del régimen privado (D.Leg. 728)
- **REMUNERATIVO** — afecta gratif, CTS, vacaciones, aportes AFP/ONP/ESSALUD, IR 5ta
- Trabajador debe presentar partida de nacimiento del hijo
""",
    },

    # ─── Horas Extra ─────────────────────────────────────────────
    {
        'titulo':      'Horas Extras (Sobretiempo)',
        'base_legal':  'Ley 27671 + DS 008-2002-TR + DS 004-2006-TR',
        'tags':        ['horas_extra', 'sobretiempo', 'he'],
        'keywords':    ['horas extra', 'horas extras', 'he 25', 'he 35', 'he 100',
                        'sobretiempo', 'feriado', 'nocturna', 'nocturno'],
        'descripcion': """\
**Horas Extras / Sobretiempo** (Ley 27671 + reglamentos):

| Tipo | Recargo | Cuándo |
|------|---------|--------|
| **HE 25%** | +25% sobre valor hora | Primeras 2 horas de sobretiempo |
| **HE 35%** | +35% | A partir de la 3ra hora (y nocturnas 22:00-06:00) |
| **HE 100%** | Doble (×2) | Trabajo en día de descanso semanal o feriado |

**Valor hora ordinaria** = sueldo / 30 / 8 (jornada estándar)

**Notas críticas:**
- HE son acuerdo trabajador-empleador, NO obligatorias
- Trabajo en feriado (DL 713) = sueldo del día + sobretasa 100% (efectivamente doble)
- Nocturno (22:00 a 06:00) sobre RMV nocturna ≥ RMV + 35%
- HE son REMUNERATIVAS — afectan gratif, CTS, vacaciones, AFP/ONP/ESSALUD, IR
""",
    },

    # ─── Subsidios ESSALUD ───────────────────────────────────────
    {
        'titulo':      'Subsidio por Incapacidad Temporal',
        'base_legal':  'Ley 26790 (Ley de Modernización Seguridad Social)',
        'tags':        ['subsidio', 'incapacidad', 'enfermedad', 'essalud'],
        'keywords':    ['subsidio incapacidad', 'incapacidad temporal', 'descanso médico',
                        'cita', 'enfermedad', 'reposo', 'cita 21'],
        'descripcion': """\
**Subsidio por Incapacidad Temporal** (Ley 26790):

| Días | Quién paga | Naturaleza |
|------|-----------|------------|
| 1 - 20 | **Empleador** | Remuneración íntegra (REMUNERATIVO — afecta todos los aportes) |
| 21 - 340 | **ESSALUD** | Subsidio (**NO REMUNERATIVO** — no descuentos) |
| > 340 días (11m10d) | No pagable | Tope legal alcanzado |

**Cálculo del subsidio diario**:
- Promedio de las remuneraciones de los últimos 12 meses ÷ 360
- Simplificación práctica: sueldo_mensual / 30

**Documento requerido**: Certificado de Incapacidad Temporal del Trabajo (CITT) emitido por médico ESSALUD.

**Trámite**: Empleador presenta CITT a ESSALUD y solicita reembolso (Formulario 8001).
""",
    },
    {
        'titulo':      'Subsidio por Maternidad',
        'base_legal':  'Ley 26790 + Ley 30367',
        'tags':        ['subsidio', 'maternidad', 'embarazo', 'essalud'],
        'keywords':    ['maternidad', 'embarazo', 'subsidio maternidad', 'pre natal',
                        'post natal', '98 días', '49 días'],
        'descripcion': """\
**Subsidio por Maternidad** (Ley 26790 + Ley 30367):
- **98 días** de licencia (49 pre-natal + 49 post-natal)
- En caso de parto múltiple o discapacidad del niño: +30 días extra
- **Paga ESSALUD** — no es remunerativo
- Trabajador debe tener **3 meses consecutivos o 4 alternados de aportes** en los últimos 6 meses (Art. 12)
- Empleador adelanta el subsidio y solicita reembolso a ESSALUD
""",
    },

    # ─── Embargo y Pensión Alimenticia ───────────────────────────
    {
        'titulo':      'Embargo de Remuneraciones',
        'base_legal':  'Art. 648 del Código Procesal Civil',
        'tags':        ['embargo', 'descuento_judicial', 'pension_alimenticia'],
        'keywords':    ['embargo', 'pensión alimenticia', 'pension alimenticia', 'alimentos',
                        '648', 'cpc', '5 urp', 'inembargable'],
        'descripcion': """\
**Embargo de Remuneraciones** (Art. 648 CPC):

**Inembargable**:
- Hasta **5 URP** (5 × RMV = S/5,650 en 2026)
- Garantiza un mínimo vital al trabajador

**Embargable sobre el exceso**:
- **Deudas comunes** (civiles): hasta **1/3 (33.33%)** del exceso sobre 5 URP
- **Pensión alimenticia**: hasta **60%** de la remuneración total (no del exceso) — Art. 648 inciso 5

**Ejemplo embargo civil sueldo 8,000**:
- Inembargable: 5,650
- Exceso: 2,350
- Máximo embargable: 2,350 ÷ 3 = **S/ 783.33**

**Ejemplo pensión alimenticia 30% sueldo 3,000**:
- Base de cálculo: sueldo total - descuentos legales (AFP/ONP, IR 5ta)
- Si descuentos = S/600 → base = S/2,400 → pensión = S/720
- Pensión va al beneficiario por consignación judicial o directa
""",
    },

    # ─── Vacaciones ─────────────────────────────────────────────
    {
        'titulo':      'Vacaciones Anuales',
        'base_legal':  'D.Leg. 713 + DS 012-92-TR',
        'tags':        ['vacaciones', 'descanso'],
        'keywords':    ['vacaciones', 'descanso anual', '30 días', 'goce vacacional',
                        'récord vacacional'],
        'descripcion': """\
**Vacaciones Anuales** (D.Leg. 713):
- **30 días calendario** después de 1 año de servicio + récord vacacional
- **Récord vacacional**: depende del régimen
  - Servicios diarios: 260 días efectivos en el año
  - Servicios indirectos: 210 días efectivos
- **Vacaciones truncas** al cese: proporcional (30/365 × días trabajados)
- Remuneración vacacional = sueldo del mes que toca (no se duplica)
- Si el trabajador NO toma vacaciones en el plazo legal: empleador debe pagar **3 sueldos** (1 sueldo vacacional + 1 sueldo de no haberlas tomado + 1 indemnización)
""",
    },

    # ─── Boleta electrónica ──────────────────────────────────────
    {
        'titulo':      'Boleta de Pago Electrónica',
        'base_legal':  'DS 009-2011-TR',
        'tags':        ['boleta', 'pdf', 'firma'],
        'keywords':    ['boleta', 'boleta electrónica', 'firma boleta', 'recibo',
                        '009-2011', 'ds 009', 'acuse recibo'],
        'descripcion': """\
**Boleta de Pago Electrónica** (DS 009-2011-TR):

**Datos obligatorios**:
- Empresa: razón social, RUC, dirección
- Trabajador: nombres, DNI, cargo, fecha ingreso, sistema pensionario
- Período: mes/año
- Ingresos (conceptos remunerativos y no remunerativos)
- Descuentos
- Aportes empleador (ESSALUD, SCTR, etc.)
- Neto a pagar

**Acuse de recibo**:
- El trabajador debe firmar (digital o física) la boleta
- Plazo: dentro del mes siguiente al pago
- **Si trabaja en local con menos de 3 trabajadores**: el empleador firma en su lugar (DS 009 art. 18-A)

**Conservación**: boletas deben guardarse 5 años (Art. 18 — plazo SUNAT/MTPE).
""",
    },
]


def buscar_normativa(query: str, top_k: int = 3) -> list:
    """
    Búsqueda simple por keyword matching + scoring.

    Algoritmo:
    1. Tokenizar query (palabras de 3+ chars)
    2. Para cada entrada en NORMATIVA: contar matches en keywords + título + tags
    3. Score = matches / total_tokens
    4. Retornar top_k entradas con score > 0
    """
    if not query:
        return []

    # Tokens query — minúsculas, sin acentos comunes
    query_lower = query.lower()
    tokens = [t for t in re.split(r'[\s,;.¿?¡!()]+', query_lower) if len(t) >= 3]
    if not tokens:
        return []

    scored = []
    for entry in NORMATIVA:
        searchable = ' '.join([
            entry['titulo'].lower(),
            ' '.join(entry.get('keywords', [])).lower(),
            ' '.join(entry.get('tags', [])).lower(),
        ])

        # Reemplazo simple de acentos en searchable (defensivo)
        searchable_no_acc = (searchable
            .replace('á', 'a').replace('é', 'e').replace('í', 'i')
            .replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n'))

        matches = sum(1 for t in tokens if t in searchable or t in searchable_no_acc)
        if matches > 0:
            scored.append((matches, entry))

    # Ordenar por score descendente
    scored.sort(key=lambda x: -x[0])

    return [
        {
            'titulo':      entry['titulo'],
            'base_legal':  entry['base_legal'],
            'tags':        entry.get('tags', []),
            'descripcion': entry['descripcion'],
            'score':       matches,
        }
        for matches, entry in scored[:top_k]
    ]
