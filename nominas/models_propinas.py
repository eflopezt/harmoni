"""
Pool de Propinas — Modelos.

Diseño documentado en `docs/internal/DISEÑO_LIQUIDACIONES_PROPINAS_ISC.md` §2.

Flujo:
  1. Configurar pool por empresa (modo, porcentaje casa, inclusiones).
  2. Definir puntos por cargo (en modo POOL_PUNTOS).
  3. Cargar `PoolPropinas` con `monto_bruto` recolectado del periodo.
  4. Ejecutar `pool.distribuir()` → genera `DistribucionPropinas` por trabajador.
  5. (Opcional) marcar `aplicado_en_nomina` cuando se aplica a una boleta.

Las propinas son concepto NO REMUNERATIVO — no afectan AFP/ONP/CTS/Gratif.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db import models, transaction
from django.utils import timezone


# ── Constantes auxiliares ──────────────────────────────────────────────────
_CENT = Decimal('0.01')


def _q(v) -> Decimal:
    """Cuantiza a 2 decimales con HALF_UP."""
    return Decimal(str(v)).quantize(_CENT, rounding=ROUND_HALF_UP)


# ══════════════════════════════════════════════════════════════════════════
# Configuración (1 por empresa)
# ══════════════════════════════════════════════════════════════════════════
class ConfiguracionPropinas(models.Model):
    """Configuración del pool de propinas por empresa (local)."""

    MODO_CHOICES = [
        ('POOL_PUNTOS', 'Pool por puntos (recomendado)'),
        ('POOL_PAREJO', 'Pool dividido parejo'),
        ('INDIVIDUAL',  'Individual (no se aplica pool)'),
    ]

    empresa = models.OneToOneField(
        'empresas.Empresa',
        on_delete=models.CASCADE,
        related_name='config_propinas',
        verbose_name='Empresa / Local',
    )
    modo = models.CharField(
        max_length=20,
        choices=MODO_CHOICES,
        default='POOL_PUNTOS',
        help_text='POOL_PUNTOS: reparto proporcional a puntos por cargo. '
                  'POOL_PAREJO: monto total dividido entre N participantes. '
                  'INDIVIDUAL: no se reparte vía pool.',
    )
    incluye_cocina = models.BooleanField(
        default=True,
        help_text='Si se incluye al personal de cocina en el reparto.',
    )
    incluye_admin = models.BooleanField(
        default=False,
        help_text='Si se incluye al personal administrativo en el reparto.',
    )
    porcentaje_casa = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0'),
        help_text='% que retiene el local del monto bruto (rotura, reposición, '
                  'gastos). Ej: 5 = 5%.',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de Propinas'
        verbose_name_plural = 'Configuraciones de Propinas'

    def __str__(self) -> str:
        return f'Propinas {self.empresa} — {self.get_modo_display()}'


# ══════════════════════════════════════════════════════════════════════════
# Puntos por cargo
# ══════════════════════════════════════════════════════════════════════════
class PuntosPropinas(models.Model):
    """Puntos asignados a cada cargo para el modo POOL_PUNTOS."""

    configuracion = models.ForeignKey(
        ConfiguracionPropinas,
        on_delete=models.CASCADE,
        related_name='puntos_por_cargo',
    )
    cargo = models.ForeignKey(
        'personal.Cargo',
        on_delete=models.CASCADE,
        related_name='puntos_propinas',
    )
    puntos = models.DecimalField(
        max_digits=4, decimal_places=2,
        default=Decimal('1.00'),
        help_text='Puntos del cargo. Ej: Mozo=3, Bartender=2.5, Cocina=1.',
    )

    class Meta:
        verbose_name = 'Puntos por Cargo'
        verbose_name_plural = 'Puntos por Cargo'
        unique_together = [('configuracion', 'cargo')]
        ordering = ['-puntos', 'cargo__nombre']

    def __str__(self) -> str:
        return f'{self.cargo} → {self.puntos} pts'


# ══════════════════════════════════════════════════════════════════════════
# Pool — recolección de un período
# ══════════════════════════════════════════════════════════════════════════
class PoolPropinas(models.Model):
    """Pool de propinas recolectado en un rango de fechas (semana/mes)."""

    empresa = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.CASCADE,
        related_name='pools_propinas',
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    monto_bruto = models.DecimalField(
        max_digits=12, decimal_places=2,
        default=Decimal('0'),
        help_text='Monto total recolectado en el período (antes de % casa).',
    )
    distribuido = models.BooleanField(default=False)
    distribuido_en = models.DateTimeField(null=True, blank=True)
    notas = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pool de Propinas'
        verbose_name_plural = 'Pools de Propinas'
        ordering = ['-fecha_fin', '-pk']
        indexes = [
            models.Index(fields=['empresa', '-fecha_fin']),
            models.Index(fields=['distribuido']),
        ]

    def __str__(self) -> str:
        return (
            f'Pool {self.empresa} {self.fecha_inicio:%d/%m/%Y}–'
            f'{self.fecha_fin:%d/%m/%Y}'
        )

    # ── Cálculos derivados ──────────────────────────────────────────────
    def _config(self) -> ConfiguracionPropinas | None:
        return ConfiguracionPropinas.objects.filter(empresa=self.empresa).first()

    @property
    def monto_casa(self) -> Decimal:
        """Monto que retiene el local según porcentaje_casa de la config."""
        cfg = self._config()
        if not cfg or not cfg.porcentaje_casa:
            return Decimal('0.00')
        return _q(
            (Decimal(self.monto_bruto) * Decimal(cfg.porcentaje_casa)) / Decimal('100')
        )

    @property
    def monto_distribuible(self) -> Decimal:
        """Monto a repartir entre el personal = bruto − casa."""
        return _q(Decimal(self.monto_bruto) - self.monto_casa)

    # ── Acción principal ────────────────────────────────────────────────
    @transaction.atomic
    def distribuir(self):
        """
        Reparte `monto_distribuible` entre los trabajadores activos del rango
        según el modo configurado.

        Crea instancias de `DistribucionPropinas` por trabajador.
        Marca el pool como `distribuido=True` con timestamp.

        Idempotente: si ya está distribuido, retorna [] sin reprocesar.
        Atómico: si falla la creación de alguna distribución, revierte todo.

        Returns
        -------
        list[DistribucionPropinas]
            Distribuciones creadas (vacío si ya estaba distribuido o modo INDIVIDUAL).
        """
        if self.distribuido:
            return []

        cfg = self._config()
        if not cfg:
            # Sin config no se puede distribuir; marcar como vacío.
            self.distribuido = True
            self.distribuido_en = timezone.now()
            self.save(update_fields=['distribuido', 'distribuido_en'])
            return []

        # Modo INDIVIDUAL no usa pool: solo marca y sale.
        if cfg.modo == 'INDIVIDUAL':
            self.distribuido = True
            self.distribuido_en = timezone.now()
            self.save(update_fields=['distribuido', 'distribuido_en'])
            return []

        # ── 1) Resolver participantes ──────────────────────────────────
        from personal.models import Personal

        qs = Personal.objects.filter(
            empresa=self.empresa,
            estado='Activo',
            fecha_alta__lte=self.fecha_fin,
        ).filter(
            models.Q(fecha_cese__isnull=True) | models.Q(fecha_cese__gte=self.fecha_inicio)
        )

        # Filtrar cocina / admin según config (heurística por nombre de cargo)
        if not cfg.incluye_cocina:
            qs = qs.exclude(cargo__icontains='cocin')
            qs = qs.exclude(cargo__icontains='chef')
            qs = qs.exclude(cargo__icontains='lavapl')
            qs = qs.exclude(cargo__icontains='ayudante de cocina')
        if not cfg.incluye_admin:
            qs = qs.exclude(cargo__icontains='admin')
            qs = qs.exclude(cargo__icontains='conta')
            qs = qs.exclude(cargo__icontains='rrhh')
            qs = qs.exclude(cargo__icontains='gerente')

        participantes = list(qs.select_related('cargo_obj'))
        if not participantes:
            self.distribuido = True
            self.distribuido_en = timezone.now()
            self.save(update_fields=['distribuido', 'distribuido_en'])
            return []

        # ── 2) Calcular puntos por participante ───────────────────────
        puntos_lookup = {
            p.cargo_id: Decimal(p.puntos)
            for p in cfg.puntos_por_cargo.all()
        }
        DEFAULT_PUNTOS = Decimal('1.00')

        puntos_por_persona = []
        for persona in participantes:
            if cfg.modo == 'POOL_PAREJO':
                pts = Decimal('1.00')
            else:  # POOL_PUNTOS
                cid = persona.cargo_obj_id
                pts = puntos_lookup.get(cid, DEFAULT_PUNTOS) if cid else DEFAULT_PUNTOS
            puntos_por_persona.append((persona, pts))

        distribuible = self.monto_distribuible
        distribuciones = []

        if cfg.modo == 'POOL_PAREJO':
            n = len(participantes)
            if n == 0:
                monto_uno = Decimal('0.00')
            else:
                monto_uno = _q(distribuible / Decimal(n))
            for persona, pts in puntos_por_persona:
                d = DistribucionPropinas.objects.create(
                    pool=self,
                    personal=persona,
                    puntos=pts,
                    monto=monto_uno,
                )
                distribuciones.append(d)
        else:  # POOL_PUNTOS
            suma_pts = sum((pts for _, pts in puntos_por_persona), Decimal('0'))
            if suma_pts == 0:
                # Fallback: si nadie tiene puntos, reparto parejo.
                n = len(participantes)
                monto_uno = _q(distribuible / Decimal(n)) if n else Decimal('0.00')
                for persona, pts in puntos_por_persona:
                    d = DistribucionPropinas.objects.create(
                        pool=self,
                        personal=persona,
                        puntos=pts,
                        monto=monto_uno,
                    )
                    distribuciones.append(d)
            else:
                for persona, pts in puntos_por_persona:
                    monto = _q((distribuible * pts) / suma_pts)
                    d = DistribucionPropinas.objects.create(
                        pool=self,
                        personal=persona,
                        puntos=pts,
                        monto=monto,
                    )
                    distribuciones.append(d)

        # ── 3) Marcar pool como distribuido ───────────────────────────
        self.distribuido = True
        self.distribuido_en = timezone.now()
        self.save(update_fields=['distribuido', 'distribuido_en'])

        return distribuciones


# ══════════════════════════════════════════════════════════════════════════
# Distribución — detalle por trabajador
# ══════════════════════════════════════════════════════════════════════════
class DistribucionPropinas(models.Model):
    """Detalle de cuánto recibe cada trabajador de un Pool."""

    pool = models.ForeignKey(
        PoolPropinas,
        on_delete=models.CASCADE,
        related_name='distribuciones',
    )
    personal = models.ForeignKey(
        'personal.Personal',
        on_delete=models.PROTECT,
        related_name='propinas_recibidas',
    )
    puntos = models.DecimalField(
        max_digits=4, decimal_places=2,
        default=Decimal('1.00'),
    )
    monto = models.DecimalField(
        max_digits=12, decimal_places=2,
        default=Decimal('0'),
    )
    aplicado_en_nomina = models.ForeignKey(
        'nominas.RegistroNomina',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='propinas_aplicadas',
        help_text='RegistroNomina donde se imputó este monto (trazabilidad).',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Distribución de Propinas'
        verbose_name_plural = 'Distribuciones de Propinas'
        ordering = ['pool', '-monto']
        indexes = [
            models.Index(fields=['pool', '-monto']),
            models.Index(fields=['personal', '-creado_en']),
        ]

    def __str__(self) -> str:
        return f'{self.personal} ← S/ {self.monto} ({self.puntos} pts)'
