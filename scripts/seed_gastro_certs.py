"""Seed demo: certificaciones BPM/HACCP/Sanitario para poblar el panel gastro.
Idempotente. Solo datos de demostración (local).
"""
from datetime import date, timedelta
from capacitaciones.models import RequerimientoCapacitacion, CertificacionTrabajador
from personal.models import Personal

REQS = [
    ('BPM - Buenas Prácticas de Manufactura', 'Certificación obligatoria de BPM para personal de cocina y servicio.', 'D.S. 007-98-SA'),
    ('HACCP - Análisis de Peligros y Puntos Críticos', 'Sistema HACCP para inocuidad alimentaria.', 'R.M. 449-2006/MINSA'),
    ('Manipulación de Alimentos - Carné Sanitario', 'Carné de manipulador de alimentos vigente.', 'D.S. 007-98-SA'),
]

reqs = []
for nombre, desc, base in REQS:
    r, _ = RequerimientoCapacitacion.objects.get_or_create(
        nombre=nombre,
        defaults=dict(descripcion=desc, aplica_todos=True, frecuencia='ANUAL',
                      horas_minimas=8, vigencia_dias=365, base_legal=base,
                      obligatorio=True, activo=True),
    )
    reqs.append(r)

hoy = date.today()
# Vencimientos variados → poblar KPIs vigente / por_vencer / vencida / faltante
# (dejamos ~20% sin cert para que 'faltante' > 0)
trabajadores = list(Personal.objects.filter(estado='Activo').order_by('apellidos_nombres')[:45])
creadas = 0
for i, emp in enumerate(trabajadores):
    if i % 5 == 4:
        continue  # 1 de cada 5 sin certificación (faltante)
    for j, req in enumerate(reqs):
        # patrón de vencimiento por índice
        mod = (i + j) % 6
        if mod in (0, 1, 2):
            venc = hoy + timedelta(days=120 + mod * 40)   # vigente
        elif mod in (3, 4):
            venc = hoy + timedelta(days=10 + mod)          # por vencer (<=30d)
        else:
            venc = hoy - timedelta(days=15)                # vencida
        obt = venc - timedelta(days=365)
        _, was_new = CertificacionTrabajador.objects.get_or_create(
            personal=emp, requerimiento=req,
            defaults=dict(fecha_obtencion=obt, fecha_vencimiento=venc,
                          estado='VIGENTE'),
        )
        if was_new:
            creadas += 1

print(f'Requerimientos gastro: {len(reqs)} | Certificaciones nuevas: {creadas}')
print(f'Total CertificacionTrabajador: {CertificacionTrabajador.objects.count()}')
