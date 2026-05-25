"""
Pool de Propinas — Modelos.

Diseño documentado en `docs/internal/DISEÑO_LIQUIDACIONES_PROPINAS_ISC.md` §2
y `docs/internal/PROPINAS_BEST_PRACTICES_2026.md` (investigación mundial).

Flujo:
  1. Configurar pool por empresa (modo, porcentaje casa, inclusiones, tip-out BOH).
  2. Definir puntos por cargo (en modos POOL_PUNTOS / POOL_PUNTOS_HORAS).
  3. Cargar `PoolPropinas` con `monto_cash` + `monto_card` recolectado del periodo
     (o `monto_bruto` para compat legacy).
  4. (Opcional) cargar `HorasTrabajadasPropinas` por persona (modos *_HORAS).
  5. Ejecutar `pool.distribuir()` → genera `DistribucionPropinas` por trabajador.
  6. (Opcional) marcar `aplicado_en_nomina` cuando se aplica a una boleta.

Las propinas son concepto NO REMUNERATIVO en Perú — no afectan AFP/ONP/CTS/Gratif.
Ref: SUNAT — recargo al consumo y propinas no son ingreso de la empresa ni
remunerativo del trabajador.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db import models, transaction
from django.utils import timezone


# ── Constantes auxiliares ──────────────────────────────────────────────────
_CENT = Decimal('0.01')
_ANOMALIA_FACTOR = Decimal('0.50')  # < 50% del promedio del cargo → flag


def _q(v) -> Decimal:
    """Cuantiza a 2 decimales con HALF_UP."""
    return Decimal(str(v)).quantize(_CENT, rounding=ROUND_HALF_UP)


# ══════════════════════════════════════════════════════════════════════════
# Configuración (1 por empresa)
# ══════════════════════════════════════════════════════════════════════════
class ConfiguracionPropinas(models.Model):
    """Configuración del pool de propinas por empresa (local).

    Modos soportados (best practice mundial — ver PROPINAS_BEST_PRACTICES_2026):
      - POOL_PUNTOS:        reparto por puntos por cargo (jerarquía/skill)
      - POOL_PAREJO:        monto / N participantes (homogéneo)
      - POOL_HORAS:         per-hour rate puro (justo si todos hacen lo mismo)
      - POOL_PUNTOS_HORAS:  híbrido puntos×horas (estado del arte — 7shifts,
                            Toast Tips Manager, TipHaus)
      - INDIVIDUAL:         no se aplica pool (cada uno se lleva lo suyo)
    """

    MODO_CHOICES = [
        ('POOL_PUNTOS',       'Pool por puntos (cargo/jerarquía)'),
        ('POOL_PAREJO',       'Pool dividido parejo'),
        ('POOL_HORAS',        'Pool por horas trabajadas'),
        ('POOL_PUNTOS_HORAS', 'Pool por puntos × horas (recomendado)'),
        ('INDIVIDUAL',        'Individual (no se aplica pool)'),
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
        help_text='POOL_PUNTOS_HORAS es la práctica mundial estándar (7shifts/Toast).',
    )
    incluye_cocina = models.BooleanField(
        default=True,
        help_text='Si se incluye al personal de cocina en el reparto (BOH).',
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
    # ── Tip-out FOH → BOH ────────────────────────────────────────────────
    porcentaje_tipout_boh = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0'),
        help_text='% del distribuible que se separa para BOH (cocina) ANTES '
                  'del reparto al FOH. Ej: 15 = 15%. Práctica US estándar '
                  '70/15/10/5. Si incluye_cocina=True este % es ignorado '
                  '(la cocina ya entra al pool principal).',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de Propinas'
        verbose_name_plural = 'Configuraciones de Propinas'

    def __str__(self) -> str:
        return f'Propinas {self.empresa} — {self.get_modo_display()}'

    @property
    def usa_horas(self) -> bool:
        """True si el modo requiere horas trabajadas."""
        return self.modo in ('POOL_HORAS', 'POOL_PUNTOS_HORAS')

    @property
    def usa_puntos(self) -> bool:
        """True si el modo requiere puntos por cargo."""
        return self.modo in ('POOL_PUNTOS', 'POOL_PUNTOS_HORAS')


# ══════════════════════════════════════════════════════════════════════════
# Puntos por cargo
# ══════════════════════════════════════════════════════════════════════════
class PuntosPropinas(models.Model):
    """Puntos asignados a cada cargo para los modos POOL_PUNTOS y
    POOL_PUNTOS_HORAS."""

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
    """Pool de propinas recolectado en un rango de fechas (turno/semana/mes).

    Sigue best practice mundial: cash vs card separados (Form 8027 US, mejor
    auditoría en Perú aunque legalmente sea no-remunerativo).
    """

    empresa = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.CASCADE,
        related_name='pools_propinas',
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    # ── Importes ────────────────────────────────────────────────────────
    monto_cash = models.DecimalField(
        max_digits=12, decimal_places=2,
        default=Decimal('0'),
        help_text='Propinas en efectivo declaradas en el período.',
    )
    monto_card = models.DecimalField(
        max_digits=12, decimal_places=2,
        default=Decimal('0'),
        help_text='Propinas vía tarjeta (capturadas por POS) en el período.',
    )
    monto_bruto = models.DecimalField(
        max_digits=12, decimal_places=2,
        default=Decimal('0'),
        help_text='Monto total bruto = cash + card. Se recalcula en save() si '
                  'cash o card están seteados; legacy para retro-compat.',
    )
    # ── Estado ──────────────────────────────────────────────────────────
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

    # ── Sync de monto_bruto ────────────────────────────────────────────
    def save(self, *args, **kwargs):
        """Mantiene `monto_bruto` consistente con `monto_cash` + `monto_card`.

        Compat:
          - Si usuario sólo seteó `monto_bruto` (legacy), lo respetamos.
          - Si seteó cash y/o card, recomputamos bruto = cash + card.
        """
        cash = Decimal(self.monto_cash or 0)
        card = Decimal(self.monto_card or 0)
        if cash > 0 or card > 0:
            self.monto_bruto = _q(cash + card)
        super().save(*args, **kwargs)

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

    @property
    def monto_tipout_boh(self) -> Decimal:
        """Porción del distribuible que va a BOH vía tip-out (cuando aplique).

        Solo aplica si `incluye_cocina=False` (BOH excluido del pool principal)
        y `porcentaje_tipout_boh > 0`.
        """
        cfg = self._config()
        if not cfg or cfg.incluye_cocina or not cfg.porcentaje_tipout_boh:
            return Decimal('0.00')
        return _q(
            (Decimal(self.monto_distribuible) * Decimal(cfg.porcentaje_tipout_boh))
            / Decimal('100')
        )

    @property
    def monto_distribuible_foh(self) -> Decimal:
        """Distribuible al FOH = distribuible − tipout BOH."""
        return _q(Decimal(self.monto_distribuible) - self.monto_tipout_boh)

    # ── Helpers de horas ────────────────────────────────────────────────
    def _horas_lookup(self) -> dict[int, Decimal]:
        """Mapa personal_id → horas registradas para este pool."""
        return {
            h.personal_id: Decimal(h.horas)
            for h in self.horas.all()
        }

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

        Comportamiento por modo:
          - INDIVIDUAL: no crea distribuciones, sólo marca pool.
          - POOL_PAREJO: monto / N (FOH; BOH recibe tip-out aparte si aplica).
          - POOL_HORAS: per-hour rate puro (horas necesarias).
          - POOL_PUNTOS: por puntos del cargo.
          - POOL_PUNTOS_HORAS: por puntos × horas (mejor práctica).

        Tip-out BOH:
          - Si `incluye_cocina=False` y `porcentaje_tipout_boh > 0`,
            se separa esa porción y se distribuye parejo entre BOH detectado
            por nombre de cargo. Si no hay BOH detectable, el monto regresa
            al pool FOH.

        Anomalías:
          - Tras distribuir, se calcula el promedio por cargo y se marca
            `anomalia=True` en distribuciones < 50% del promedio de su cargo
            (con al menos 2 personas en el cargo y monto > 0).

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

        qs_base = Personal.objects.filter(
            empresa=self.empresa,
            estado='Activo',
            fecha_alta__lte=self.fecha_fin,
        ).filter(
            models.Q(fecha_cese__isnull=True) | models.Q(fecha_cese__gte=self.fecha_inicio)
        )

        # Identificar BOH (cocina) y admin por nombre de cargo (heurística)
        boh_kw = ('cocin', 'chef', 'lavapl', 'ayudante de cocina')
        admin_kw = ('admin', 'conta', 'rrhh', 'gerente')

        def _es_boh(persona) -> bool:
            nombre = (persona.cargo or '').lower()
            return any(k in nombre for k in boh_kw)

        def _es_admin(persona) -> bool:
            nombre = (persona.cargo or '').lower()
            return any(k in nombre for k in admin_kw)

        # Filtrar admin siempre que no esté incluido
        qs_pool = qs_base
        if not cfg.incluye_admin:
            for k in admin_kw:
                qs_pool = qs_pool.exclude(cargo__icontains=k)

        # Filtrar cocina solo si NO está incluida en el pool principal
        if not cfg.incluye_cocina:
            for k in boh_kw:
                qs_pool = qs_pool.exclude(cargo__icontains=k)

        participantes = list(qs_pool.select_related('cargo_obj'))

        # Separar BOH para tip-out (si aplica)
        tipout_boh_monto = self.monto_tipout_boh
        distribuible_foh = self.monto_distribuible_foh
        boh_para_tipout = []
        if tipout_boh_monto > 0 and not cfg.incluye_cocina:
            # Reusar qs_base sin la exclusión de cocina, para detectar BOH
            qs_boh = qs_base
            if not cfg.incluye_admin:
                for k in admin_kw:
                    qs_boh = qs_boh.exclude(cargo__icontains=k)
            boh_para_tipout = [p for p in qs_boh if _es_boh(p)]
            if not boh_para_tipout:
                # No hay BOH detectable → tip-out regresa al pool FOH
                distribuible_foh = self.monto_distribuible
                tipout_boh_monto = Decimal('0.00')

        if not participantes and not boh_para_tipout:
            self.distribuido = True
            self.distribuido_en = timezone.now()
            self.save(update_fields=['distribuido', 'distribuido_en'])
            return []

        # ── 2) Cálculo de horas y puntos por participante (FOH) ───────
        horas_lookup = self._horas_lookup()
        puntos_lookup = {
            p.cargo_id: Decimal(p.puntos)
            for p in cfg.puntos_por_cargo.all()
        }
        DEFAULT_PUNTOS = Decimal('1.00')
        DEFAULT_HORAS = Decimal('1.00')  # fallback si no hay registro de horas

        def _puntos_de(persona):
            cid = persona.cargo_obj_id
            return puntos_lookup.get(cid, DEFAULT_PUNTOS) if cid else DEFAULT_PUNTOS

        def _horas_de(persona):
            return horas_lookup.get(persona.pk, DEFAULT_HORAS)

        distribuciones = []
        modo = cfg.modo

        # ── 3) Distribuir al FOH según modo ───────────────────────────
        if participantes:
            n = len(participantes)
            if modo == 'POOL_PAREJO':
                monto_uno = _q(distribuible_foh / Decimal(n)) if n else Decimal('0.00')
                for persona in participantes:
                    d = DistribucionPropinas.objects.create(
                        pool=self,
                        personal=persona,
                        puntos=Decimal('1.00'),
                        horas=_horas_de(persona) if cfg.usa_horas else Decimal('0.00'),
                        monto=monto_uno,
                    )
                    distribuciones.append(d)

            elif modo == 'POOL_HORAS':
                # per-hour rate puro
                pesos = [(persona, _horas_de(persona)) for persona in participantes]
                suma = sum((h for _, h in pesos), Decimal('0'))
                if suma <= 0:
                    # Fallback: reparto parejo si nadie tiene horas válidas
                    monto_uno = _q(distribuible_foh / Decimal(n)) if n else Decimal('0.00')
                    for persona in participantes:
                        d = DistribucionPropinas.objects.create(
                            pool=self, personal=persona,
                            puntos=Decimal('1.00'),
                            horas=Decimal('0.00'),
                            monto=monto_uno,
                        )
                        distribuciones.append(d)
                else:
                    for persona, h in pesos:
                        monto = _q((distribuible_foh * h) / suma)
                        d = DistribucionPropinas.objects.create(
                            pool=self, personal=persona,
                            puntos=Decimal('1.00'),
                            horas=h,
                            monto=monto,
                        )
                        distribuciones.append(d)

            elif modo == 'POOL_PUNTOS_HORAS':
                # peso = puntos × horas
                pesos = [
                    (persona, _puntos_de(persona), _horas_de(persona))
                    for persona in participantes
                ]
                suma = sum((p * h for _, p, h in pesos), Decimal('0'))
                if suma <= 0:
                    monto_uno = _q(distribuible_foh / Decimal(n)) if n else Decimal('0.00')
                    for persona, p, h in pesos:
                        d = DistribucionPropinas.objects.create(
                            pool=self, personal=persona,
                            puntos=p, horas=h, monto=monto_uno,
                        )
                        distribuciones.append(d)
                else:
                    for persona, p, h in pesos:
                        peso = p * h
                        monto = _q((distribuible_foh * peso) / suma)
                        d = DistribucionPropinas.objects.create(
                            pool=self, personal=persona,
                            puntos=p, horas=h, monto=monto,
                        )
                        distribuciones.append(d)

            else:  # POOL_PUNTOS (legacy)
                pesos = [(persona, _puntos_de(persona)) for persona in participantes]
                suma = sum((p for _, p in pesos), Decimal('0'))
                if suma <= 0:
                    monto_uno = _q(distribuible_foh / Decimal(n)) if n else Decimal('0.00')
                    for persona, p in pesos:
                        d = DistribucionPropinas.objects.create(
                            pool=self, personal=persona,
                            puntos=p, horas=Decimal('0.00'),
                            monto=monto_uno,
                        )
                        distribuciones.append(d)
                else:
                    for persona, p in pesos:
                        monto = _q((distribuible_foh * p) / suma)
                        d = DistribucionPropinas.objects.create(
                            pool=self, personal=persona,
                            puntos=p, horas=Decimal('0.00'),
                            monto=monto,
                        )
                        distribuciones.append(d)

        # ── 4) Tip-out BOH (si aplica) ────────────────────────────────
        if tipout_boh_monto > 0 and boh_para_tipout:
            n_boh = len(boh_para_tipout)
            monto_uno_boh = _q(tipout_boh_monto / Decimal(n_boh))
            for persona in boh_para_tipout:
                d = DistribucionPropinas.objects.create(
                    pool=self, personal=persona,
                    puntos=Decimal('1.00'),
                    horas=_horas_de(persona) if cfg.usa_horas else Decimal('0.00'),
                    monto=monto_uno_boh,
                    es_tipout_boh=True,
                )
                distribuciones.append(d)

        # ── 5) Detección de anomalías por cargo ───────────────────────
        if distribuciones:
            por_cargo: dict[str, list[DistribucionPropinas]] = {}
            for d in distribuciones:
                if d.es_tipout_boh:
                    continue  # tip-out es parejo, no aplica anomalía
                cargo_nombre = (d.personal.cargo or '_').lower().strip()
                por_cargo.setdefault(cargo_nombre, []).append(d)

            ids_anomalos: list[int] = []
            for cargo_nombre, grupo in por_cargo.items():
                if len(grupo) < 2:
                    continue
                montos = [d.monto for d in grupo]
                promedio = sum(montos, Decimal('0')) / Decimal(len(montos))
                if promedio <= 0:
                    continue
                umbral = promedio * _ANOMALIA_FACTOR
                for d in grupo:
                    if d.monto > 0 and d.monto < umbral:
                        d.anomalia = True
                        ids_anomalos.append(d.pk)

            if ids_anomalos:
                DistribucionPropinas.objects.filter(pk__in=ids_anomalos).update(
                    anomalia=True,
                )

        # ── 6) Marcar pool como distribuido ───────────────────────────
        self.distribuido = True
        self.distribuido_en = timezone.now()
        self.save(update_fields=['distribuido', 'distribuido_en'])

        return distribuciones


# ══════════════════════════════════════════════════════════════════════════
# Horas trabajadas por persona en el pool (modos *_HORAS)
# ══════════════════════════════════════════════════════════════════════════
class HorasTrabajadasPropinas(models.Model):
    """Horas trabajadas por persona en el período de un Pool.

    Carga manual (puede integrarse con asistencia más adelante).
    Solo se usa cuando `ConfiguracionPropinas.modo` es POOL_HORAS o
    POOL_PUNTOS_HORAS.
    """

    pool = models.ForeignKey(
        PoolPropinas,
        on_delete=models.CASCADE,
        related_name='horas',
    )
    personal = models.ForeignKey(
        'personal.Personal',
        on_delete=models.CASCADE,
        related_name='horas_pool_propinas',
    )
    horas = models.DecimalField(
        max_digits=6, decimal_places=2,
        default=Decimal('0'),
        help_text='Horas trabajadas en el período del pool. Ej: 42.50.',
    )

    class Meta:
        verbose_name = 'Horas trabajadas (Pool Propinas)'
        verbose_name_plural = 'Horas trabajadas (Pool Propinas)'
        unique_together = [('pool', 'personal')]
        indexes = [
            models.Index(fields=['pool', 'personal']),
        ]

    def __str__(self) -> str:
        return f'{self.personal} — {self.horas}h en pool {self.pool_id}'


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
    horas = models.DecimalField(
        max_digits=6, decimal_places=2,
        default=Decimal('0.00'),
        help_text='Horas usadas en el cálculo (modos *_HORAS).',
    )
    monto = models.DecimalField(
        max_digits=12, decimal_places=2,
        default=Decimal('0'),
    )
    es_tipout_boh = models.BooleanField(
        default=False,
        help_text='True si la distribución corresponde al tip-out hacia BOH '
                  '(cocina), separado del pool principal.',
    )
    anomalia = models.BooleanField(
        default=False,
        help_text='True si el monto recibido es < 50% del promedio del cargo. '
                  'Útil para revisar manualmente antes de pagar (best practice '
                  'TipHaus / Toast).',
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
            models.Index(fields=['anomalia']),
        ]

    def __str__(self) -> str:
        tag = ' [TIP-OUT]' if self.es_tipout_boh else ''
        return f'{self.personal} ← S/ {self.monto} ({self.puntos} pts){tag}'
