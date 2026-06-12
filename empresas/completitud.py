"""
Completitud de datos de la empresa.

Los archivos SUNAT (T-Registro, PLAME), las boletas y los contratos usan
datos de la ficha de la empresa. Si faltan, los archivos salen incompletos
o inválidos — y el cliente no tiene forma obvia de saberlo hasta que SUNAT
rechaza el archivo. Este módulo centraliza la verificación y alimenta:

  - el wizard /empresas/<pk>/datos/ (página única para completar todo),
  - el Centro de Acción del home (aviso con conteo de faltantes),
  - el validador de onboarding (que antes mandaba al admin de Django).

`datos_pendientes(empresa)` devuelve los campos faltantes con severidad:
  - CRITICO: rompe archivos SUNAT o deja boletas/contratos sin validez
  - RECOMENDADO: el documento sale, pero incompleto o genérico
"""


def _item(campo, label, motivo):
    return {'campo': campo, 'label': label, 'motivo': motivo}


def datos_pendientes(empresa):
    """Evalúa la ficha de la empresa. Devuelve dict con listas `criticos`
    y `recomendados`, el total y el flag `completo` (sin críticos)."""
    criticos = []
    recomendados = []

    ruc = (empresa.ruc or '').strip()
    if not (len(ruc) == 11 and ruc.isdigit()):
        criticos.append(_item(
            'ruc', 'RUC válido (11 dígitos)',
            'Sin RUC válido, T-Registro y PLAME son rechazados por SUNAT.'))
    if not (empresa.razon_social or '').strip():
        criticos.append(_item(
            'razon_social', 'Razón social',
            'Aparece en blanco en boletas, contratos y archivos SUNAT.'))
    if not (empresa.direccion or '').strip():
        criticos.append(_item(
            'direccion', 'Dirección fiscal',
            'Requerida en boletas de pago y T-Registro.'))
    if not (empresa.representante_legal or '').strip():
        criticos.append(_item(
            'representante_legal', 'Representante legal',
            'Las boletas y contratos salen sin firmante responsable.'))
    if not (empresa.nro_doc_representante or '').strip():
        criticos.append(_item(
            'nro_doc_representante', 'Documento del representante',
            'Los contratos requieren identificar al firmante.'))

    ubigeo = (empresa.ubigeo or '').strip()
    if not (len(ubigeo) == 6 and ubigeo.isdigit()):
        recomendados.append(_item(
            'ubigeo', 'Ubigeo (6 dígitos)',
            'SUNAT lo usa para ubicar el domicilio fiscal.'))
    if not (empresa.distrito or '').strip():
        recomendados.append(_item(
            'distrito', 'Distrito / Provincia / Departamento',
            'Completa la dirección fiscal en documentos oficiales.'))
    if not (empresa.actividad_economica or '').strip():
        recomendados.append(_item(
            'actividad_economica', 'Actividad económica (CIIU)',
            'Se declara en el T-Registro del empleador.'))
    if not (empresa.cargo_representante or '').strip():
        recomendados.append(_item(
            'cargo_representante', 'Cargo del representante',
            'Ej. Gerente General — aparece junto a la firma.'))
    if not empresa.logo:
        recomendados.append(_item(
            'logo', 'Logotipo',
            'Las boletas y reportes PDF se ven genéricos sin logo.'))
    if not (empresa.telefono or '').strip():
        recomendados.append(_item(
            'telefono', 'Teléfono de contacto',
            'Aparece en constancias y comunicaciones.'))
    if not (empresa.email_rrhh or '').strip():
        recomendados.append(_item(
            'email_rrhh', 'Email de RRHH',
            'Destino de respuestas de trabajadores y notificaciones.'))

    return {
        'criticos': criticos,
        'recomendados': recomendados,
        'total_pendientes': len(criticos) + len(recomendados),
        'completo': not criticos,
    }
