"""
Completa los campos vacios de los empleados ya cargados en la empresa activa.

Rellena de forma realista y determinista (sin aleatorio puro — usa el DNI como
semilla para que la misma persona siempre obtenga los mismos valores):
  - cuspp           Codigo AFP
  - banco           Banco de sueldo
  - cuenta_ahorros  Numero de cuenta sueldo
  - cuenta_cci      CCI 20 digitos
  - cuenta_cts      Cuenta CTS (banco diferente, opcional)
  - correo_corporativo   nombre.apellido@<dominio_empresa>
  - tipo_contrato   Modalidad segun antiguedad
  - regimen_laboral D.Leg. 728 (privado) o Microempresa
  - ubigeo          Lima / provincias (datos Peru)

Solo toca campos que esten vacios — no sobreescribe nada.

Uso:
    python manage.py seed_demo_completar
    python manage.py seed_demo_completar --forzar   (sobreescribe todo)
    python manage.py seed_demo_completar --dominio grupoandino.com.pe
"""
import re
import unicodedata
import random
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from personal.models import Personal
from asistencia.models import ConfiguracionSistema


# ---------------------------------------------------------------------------
# Helpers deterministicos — usa hash del DNI como semilla
# ---------------------------------------------------------------------------

def _seed(nro_doc: str) -> random.Random:
    """RNG semillado con el DNI para reproducibilidad."""
    rng = random.Random(int(nro_doc) if nro_doc.isdigit() else hash(nro_doc))
    return rng


def _normalizar(texto: str) -> str:
    """Remueve tildes y convierte a minusculas ASCII."""
    nfkd = unicodedata.normalize('NFKD', texto)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _nombre_para_correo(apellidos_nombres: str) -> str:
    """
    'GUTIERREZ SANCHEZ, Valeria Cristina' -> 'valeria.gutierrez'
    Toma primer nombre + primer apellido.
    """
    try:
        partes = apellidos_nombres.split(',')
        apellidos = partes[0].strip().split()
        nombres   = partes[1].strip().split() if len(partes) > 1 else []
        primer_nombre   = _normalizar(nombres[0])   if nombres   else 'usuario'
        primer_apellido = _normalizar(apellidos[0]) if apellidos else 'empresa'
        # Eliminar caracteres no ASCII
        primer_nombre   = re.sub(r'[^a-z0-9]', '', primer_nombre)
        primer_apellido = re.sub(r'[^a-z0-9]', '', primer_apellido)
        return f'{primer_nombre}.{primer_apellido}'
    except Exception:
        return 'empleado'


# ---------------------------------------------------------------------------
# Tablas de datos Peru
# ---------------------------------------------------------------------------

# (prefijo_CCI_3dig, nombre_banco, len_cuenta_ahorros)
BANCOS = [
    ('002', 'BCP',               13),
    ('011', 'BBVA',              18),
    ('003', 'Interbank',         13),
    ('009', 'Scotiabank',        10),
    ('018', 'Banco de la Nacion', 13),
    ('016', 'Falabella',         12),
]

# Prefijos CUSPP por AFP (4 letras + 8 alfanumericos = 12 total)
AFP_CUSPP_PREFIX = {
    'Integra':   'INTG',
    'Prima':     'PRIM',
    'Profuturo': 'PRFU',
    'Habitat':   'HABI',
}

# Ubigeos Lima (mas comunes en Lima Metropolitana)
UBIGEOS_LIMA = [
    '150101',  # Lima - Lima
    '150102',  # Lima - Ate
    '150104',  # Lima - Carabayllo
    '150105',  # Lima - Breña
    '150106',  # Lima - Chorrillos
    '150108',  # Lima - Comas
    '150113',  # Lima - Independencia
    '150116',  # Lima - La Molina
    '150118',  # Lima - Los Olivos
    '150119',  # Lima - Lurigancho
    '150122',  # Lima - Miraflores
    '150130',  # Lima - San Martin de Porres
    '150131',  # Lima - San Isidro
    '150132',  # Lima - San Juan de Lurigancho
    '150140',  # Lima - Santiago de Surco
    '150141',  # Lima - Villa Maria del Triunfo
    '150142',  # Lima - Villa El Salvador
    '070101',  # Callao
    '070102',  # Callao - Bellavista
    '070106',  # Callao - Ventanilla
]

# Para empleados con condicion != LOCAL (foraneos tipicos)
UBIGEOS_PROVINCIAS = [
    '010101',  # Abancay, Apurimac
    '020101',  # Huaraz, Ancash
    '030101',  # Abancay (dup, reemplazar)
    '040101',  # Arequipa
    '050101',  # Ayacucho
    '060101',  # Cajamarca
    '080101',  # Cusco
    '090101',  # Huancavelica
    '100101',  # Huanuco
    '110101',  # Ica
    '120101',  # Junin
    '130101',  # Trujillo, La Libertad
    '140101',  # Chiclayo, Lambayeque
    '150401',  # Barranca, Lima region
    '160101',  # Iquitos, Loreto
    '170101',  # Moyobamba, San Martin
    '180101',  # Tacna
    '190101',  # Tumbes
    '200101',  # Puno
    '210101',  # Piura
]

# Regimenes laborales Peru (texto libre en el modelo)
REGIMENES = [
    'D.Leg. 728',      # Privado general — el mas comun
    'D.Leg. 728',      # Repetido para mayor peso
    'D.Leg. 728',
    'Microempresa',    # Menos comun
]


# ---------------------------------------------------------------------------
# Funciones de generacion
# ---------------------------------------------------------------------------

def _generar_cuspp(afp: str, nro_doc: str) -> str:
    """
    CUSPP formato Peru: 4 letras AFP + 8 alfanumericos = 12 chars.
    Usa parte del DNI para realismo.
    """
    prefijo = AFP_CUSPP_PREFIX.get(afp, 'AFPX')
    rng = _seed(nro_doc)
    sufijo_digitos = nro_doc[-4:] if len(nro_doc) >= 4 else nro_doc
    letras = ''.join(rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ') for _ in range(2))
    numeros = ''.join(str(rng.randint(0, 9)) for _ in range(2))
    return f'{prefijo}{letras}{sufijo_digitos}{numeros}'[:12]


def _generar_banco(nro_doc: str) -> tuple[str, str, str, str]:
    """
    Retorna (banco, cuenta_ahorros, cuenta_cci, cuenta_cts).
    banco_cts puede ser diferente al principal.
    """
    rng = _seed(nro_doc)
    cci_prefix, banco_nombre, cuenta_len = rng.choice(BANCOS)

    # Cuenta sueldo
    cuenta = ''.join(str(rng.randint(0, 9)) for _ in range(cuenta_len))

    # CCI: 3 (banco) + 3 (agencia) + 10 (cuenta) + 2 (control) = 18... pero Peru usa 20
    # Formato real: 3_banco + 3_agencia + 10_cuenta + 2_moneda + 2_digcontrol
    # Simplificado para demo:
    agencia  = ''.join(str(rng.randint(0, 9)) for _ in range(3))
    cuenta20 = cuenta.ljust(10, '0')[:10]
    moneda   = '00'
    control  = str(rng.randint(10, 99))
    cci = f'{cci_prefix}{agencia}{cuenta20}{moneda}{control}'
    cci = cci[:20].ljust(20, '0')

    # CTS — banco distinto con prob 60%, mismo banco con 40%
    if rng.random() < 0.6:
        other_bancos = [b for b in BANCOS if b[0] != cci_prefix]
        _, _, cts_len = rng.choice(other_bancos) if other_bancos else (cci_prefix, banco_nombre, cuenta_len)
    else:
        cts_len = cuenta_len
    cuenta_cts = ''.join(str(rng.randint(0, 9)) for _ in range(cts_len))

    return banco_nombre, cuenta, cci, cuenta_cts


def _generar_tipo_contrato(fecha_alta: date, cargo: str, rng: random.Random) -> str:
    """
    - Gerentes/jefes -> INDEFINIDO
    - Antiguedad > 3 años -> INDEFINIDO
    - Resto: mezcla PLAZO_FIJO / INDEFINIDO / OBRA_SERVICIO
    """
    cargo_lower = cargo.lower()
    if any(kw in cargo_lower for kw in ['gerente', 'jefe', 'director', 'subgerente', 'coordinador']):
        return 'INDEFINIDO'

    if fecha_alta and (date.today() - fecha_alta).days > 365 * 3:
        return 'INDEFINIDO'

    return rng.choice(['INDEFINIDO', 'INDEFINIDO', 'PLAZO_FIJO', 'PLAZO_FIJO', 'OBRA_SERVICIO'])


def _generar_ubigeo(condicion: str, nro_doc: str) -> str:
    rng = _seed(nro_doc + 'ubigeo')
    if condicion in ('FORANEO', 'ROTATIVO'):
        pool = UBIGEOS_PROVINCIAS + UBIGEOS_LIMA[:5]
    else:
        pool = UBIGEOS_LIMA
    return rng.choice(pool)


# ---------------------------------------------------------------------------
# Comando principal
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Completa campos vacios de empleados con data peruana realista.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--forzar', action='store_true',
            help='Sobreescribe campos aunque ya tengan valor.',
        )
        parser.add_argument(
            '--dominio', default='',
            help='Dominio para correos corporativos (ej: grupoandino.com.pe). '
                 'Si no se indica, se genera desde la empresa activa.',
        )

    def handle(self, *args, **options):
        forzar = options['forzar']
        dominio_arg = options['dominio'].strip()

        # Obtener empresa activa y dominio para correos
        config = ConfiguracionSistema.get()
        empresa_nombre = config.empresa_nombre or 'empresa'

        if dominio_arg:
            dominio = dominio_arg
        else:
            # Generar dominio desde nombre empresa: "Grupo Andino SAC" -> "grupoandino.com.pe"
            base = re.sub(r'\b(SAC|SRL|SA|EIRL|SAS|LTDA|S\.A\.C\.?)\b', '', empresa_nombre, flags=re.I)
            base = re.sub(r'[^a-zA-Z0-9 ]', '', base).strip()
            slug = _normalizar(base).replace(' ', '')
            slug = re.sub(r'[^a-z0-9]', '', slug)
            dominio = f'{slug}.com.pe' if slug else 'empresa.com.pe'

        self.stdout.write(f'\n=== seed_demo_completar — empresa: {empresa_nombre} ===')
        self.stdout.write(f'    Dominio correos: @{dominio}')
        self.stdout.write(f'    Modo: {"FORZAR (sobreescribe)" if forzar else "SOLO vacios"}\n')

        empleados = Personal.objects.filter(estado='Activo').order_by('id')
        total = empleados.count()
        actualizados = 0
        sin_cambios = 0

        with transaction.atomic():
            for p in empleados:
                rng = _seed(p.nro_doc)
                cambios = {}

                # 1. CUSPP
                if (forzar or not p.cuspp) and p.regimen_pension == 'AFP' and p.afp:
                    cambios['cuspp'] = _generar_cuspp(p.afp, p.nro_doc)

                # 2. Banco + cuentas
                if forzar or not p.banco:
                    banco, cuenta, cci, cts = _generar_banco(p.nro_doc)
                    cambios['banco']          = banco
                    cambios['cuenta_ahorros'] = cuenta
                    cambios['cuenta_cci']     = cci
                    cambios['cuenta_cts']     = cts
                else:
                    # Si tiene banco pero le falta cci/cuenta
                    if not p.cuenta_ahorros or forzar:
                        _, cuenta, cci, cts = _generar_banco(p.nro_doc)
                        cambios['cuenta_ahorros'] = cuenta
                        cambios['cuenta_cci']     = cci
                        cambios['cuenta_cts']     = cts

                # 3. Correo corporativo
                if forzar or not p.correo_corporativo:
                    alias = _nombre_para_correo(p.apellidos_nombres)
                    cambios['correo_corporativo'] = f'{alias}@{dominio}'

                # 4. Tipo contrato
                if forzar or not p.tipo_contrato:
                    cambios['tipo_contrato'] = _generar_tipo_contrato(
                        p.fecha_alta, p.cargo or '', rng
                    )

                # 5. Regimen laboral
                if forzar or not p.regimen_laboral:
                    cambios['regimen_laboral'] = rng.choice(REGIMENES)

                # 6. Ubigeo
                if forzar or not p.ubigeo:
                    cambios['ubigeo'] = _generar_ubigeo(p.condicion, p.nro_doc)

                if cambios:
                    for campo, valor in cambios.items():
                        setattr(p, campo, valor)
                    p.save(update_fields=list(cambios.keys()))
                    actualizados += 1
                    self.stdout.write(
                        f'  [OK] {p.nro_doc} | {p.apellidos_nombres[:35]:35} | '
                        f'{", ".join(cambios.keys())}'
                    )
                else:
                    sin_cambios += 1

        self.stdout.write(
            f'\nListo: {actualizados} actualizados, {sin_cambios} sin cambios '
            f'(total {total} empleados activos).'
        )
        self.stdout.write(f'Dominio usado: @{dominio}')
