"""
Vista del organigrama interactivo con exportación PDF y gestión de jerarquía.
"""
import json
import re
from collections import defaultdict
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from ..models import Area, SubArea, Personal

solo_admin = user_passes_test(lambda u: u.is_superuser, login_url='login')


@login_required
@solo_admin
def organigrama_view(request):
    """Renderiza la página del organigrama interactivo."""
    areas = Area.objects.filter(activa=True).order_by('nombre')
    return render(request, 'personal/organigrama.html', {
        'titulo': 'Organigrama',
        'areas': areas,
    })


@login_required
@solo_admin
def organigrama_data(request):
    """
    API JSON para el organigrama. Construye la jerarquía con prioridad:
    1. Personal.reporta_a (explícito) si está definido.
    2. Area.jefe_area (si la persona no es ese jefe).
    3. INFERENCIA por nivel_org/cargo:
       - Dentro del área, cada persona reporta al nivel jerárquico inmediato superior.
       - El "jefe de área" inferido (cargo más alto del área) reporta al GG global.
       - El GG global (nivel 'GG') es la raíz; si no existe, todos cuelgan del _root.

    Esto garantiza que SIEMPRE se renderice como árbol vertical jerárquico,
    incluso si los campos reporta_a/jefe_area no están poblados en BD.
    """
    area_id = request.GET.get('area')  # Filtro opcional por área

    qs = Personal.objects.filter(estado='Activo').select_related(
        'subarea__area', 'reporta_a'
    )
    if area_id:
        qs = qs.filter(subarea__area_id=area_id)

    qs = list(qs)  # materializar para múltiples pasadas

    # Construir mapa de jefes de área (explícitos)
    areas_qs = Area.objects.filter(activa=True).select_related('jefe_area')
    jefe_area_map = {}  # area_id -> personal_id del jefe
    for a in areas_qs:
        if a.jefe_area_id:
            jefe_area_map[a.id] = a.jefe_area_id

    # ── Orden de niveles jerárquicos (menor índice = más alto) ──
    NIVEL_RANK = {
        'GG': 0, 'CTA': 1, 'DIR': 2, 'GER': 3,
        'JEFE_SR': 4, 'JEFE': 5, 'ESP': 6, 'ASIST': 7,
        'LIBERTY': 6, 'EXPAT': 6,
    }
    def _rank(nivel):
        return NIVEL_RANK.get(nivel, 8)

    # Calcular nivel efectivo de cada persona (explícito o derivado de cargo)
    nivel_de = {}
    for p in qs:
        nivel_de[p.id] = p.nivel_org or _detectar_nivel_org(p.cargo)

    # ── Detectar Gerente General global (el de menor rank, prefiriendo 'GG') ──
    candidatos_gg = [p for p in qs if nivel_de[p.id] == 'GG']
    if candidatos_gg:
        # Si hay varios "GG", elegir el de menor id (estable)
        gg = sorted(candidatos_gg, key=lambda x: x.id)[0]
    else:
        # No hay GG explícito → tomar el de cargo más alto globalmente
        gg = sorted(qs, key=lambda x: (_rank(nivel_de[x.id]), x.id))[0] if qs else None
    gg_id = gg.id if gg else None

    # ── Para cada área, identificar al "líder efectivo" (jefe inferido) ──
    # Prioridad: Area.jefe_area > persona de nivel más alto del área
    lider_de_area = {}  # area_id -> personal_id
    personas_por_area = defaultdict(list)
    for p in qs:
        aid = p.subarea.area_id if p.subarea_id and p.subarea and p.subarea.area_id else None
        if aid:
            personas_por_area[aid].append(p)

    for aid, personas in personas_por_area.items():
        if aid in jefe_area_map and any(pp.id == jefe_area_map[aid] for pp in personas):
            lider_de_area[aid] = jefe_area_map[aid]
        else:
            # Elegir persona de menor rank (más alto cargo). Empate → menor id.
            lider = sorted(personas, key=lambda x: (_rank(nivel_de[x.id]), x.id))[0]
            lider_de_area[aid] = lider.id

    # ── Construir nodos con parentId inferido ──
    nodes = []
    ids_incluidos = set()

    for p in qs:
        nivel = nivel_de[p.id]
        node = {
            'id': str(p.id),
            'parentId': '',
            'name': p.apellidos_nombres or '',
            'position': p.cargo or '',
            'area': p.subarea.area.nombre if p.subarea and p.subarea.area else '',
            'subarea': p.subarea.nombre if p.subarea else '',
            'dni': p.nro_doc or '',
            'grupo': p.grupo_tareo or '',
            'email': p.correo_personal or '',
            'email_corp': p.correo_corporativo or '',
            'celular': p.celular or '',
            'estado': p.estado,
            'es_jefe': False,
            'nivel': nivel,
            'personal_clave': p.personal_clave,
        }

        aid = p.subarea.area_id if p.subarea_id and p.subarea and p.subarea.area_id else None
        es_lider_area = (aid is not None and lider_de_area.get(aid) == p.id)
        if es_lider_area:
            node['es_jefe'] = True

        parent_id = None

        # 1) reporta_a explícito (máxima prioridad, evitando auto-referencia)
        if p.reporta_a_id and p.reporta_a_id != p.id:
            parent_id = p.reporta_a_id

        # 2) Si es el líder del área → reporta al GG (o a quedará en raíz)
        elif es_lider_area:
            if gg_id and gg_id != p.id:
                parent_id = gg_id
            # else: queda como raíz (el GG mismo, o no hay GG)

        # 3) Inferencia intra-área por nivel jerárquico
        elif aid and aid in personas_por_area:
            mi_rank = _rank(nivel)
            # Buscar candidato superior: en la MISMA área con rank estrictamente menor
            superiores = [
                pp for pp in personas_por_area[aid]
                if pp.id != p.id and _rank(nivel_de[pp.id]) < mi_rank
            ]
            if superiores:
                # Elegir el de rank más cercano (mayor rank dentro de los superiores)
                superiores.sort(key=lambda x: (-_rank(nivel_de[x.id]), x.id))
                parent_id = superiores[0].id
            else:
                # No hay superior intra-área → reportar al líder del área
                lider_id = lider_de_area.get(aid)
                if lider_id and lider_id != p.id:
                    parent_id = lider_id
                elif gg_id and gg_id != p.id:
                    parent_id = gg_id

        # 4) Sin área → cuelga del GG (o root)
        else:
            if gg_id and gg_id != p.id:
                parent_id = gg_id

        if parent_id:
            node['parentId'] = str(parent_id)

        nodes.append(node)
        ids_incluidos.add(p.id)

    # Incluir padres referenciados explícitamente que falten (por reporta_a a alguien fuera del filtro)
    parent_ids_faltantes = set()
    for n in nodes:
        if n['parentId']:
            try:
                pid = int(n['parentId'])
                if pid not in ids_incluidos:
                    parent_ids_faltantes.add(pid)
            except (ValueError, TypeError):
                pass

    if parent_ids_faltantes:
        for p in Personal.objects.filter(id__in=parent_ids_faltantes, estado='Activo'):
            nivel = p.nivel_org or _detectar_nivel_org(p.cargo)
            nodes.append({
                'id': str(p.id),
                'parentId': '',
                'name': p.apellidos_nombres or '',
                'position': p.cargo or '',
                'area': p.subarea.area.nombre if p.subarea and p.subarea.area else '',
                'subarea': p.subarea.nombre if p.subarea else '',
                'dni': p.nro_doc or '',
                'grupo': p.grupo_tareo or '',
                'email': p.correo_personal or '',
                'email_corp': p.correo_corporativo or '',
                'celular': p.celular or '',
                'estado': p.estado,
                'es_jefe': True,
                'nivel': nivel,
                'personal_clave': p.personal_clave,
            })
            ids_incluidos.add(p.id)

    # ── Nodo raíz virtual: la empresa ──
    # d3-org-chart requiere exactamente UN nodo raíz (parentId='')
    # Sanitizar: si un parentId apunta a un nodo que NO existe en el set, limpiar
    all_ids = {n['id'] for n in nodes}
    for n in nodes:
        if n['parentId'] and n['parentId'] not in all_ids:
            n['parentId'] = ''  # se reasignará al root abajo

    # ── Detectar y romper ciclos (defensa contra reporta_a circulares) ──
    parent_map = {n['id']: n['parentId'] for n in nodes}
    for n in nodes:
        visitados = set()
        actual = n['id']
        while actual and actual in parent_map and parent_map[actual]:
            siguiente = parent_map[actual]
            if siguiente in visitados or siguiente == n['id']:
                # Ciclo detectado: cortar a raíz
                n['parentId'] = ''
                parent_map[n['id']] = ''
                break
            visitados.add(siguiente)
            actual = siguiente
            if len(visitados) > 50:  # límite de seguridad
                n['parentId'] = ''
                parent_map[n['id']] = ''
                break

    # Nombre dinámico de la empresa (primera empresa activa)
    empresa_nombre = 'Empresa'
    try:
        from empresas.models import Empresa
        emp = Empresa.objects.filter(activa=True).first() if hasattr(Empresa, 'objects') else None
        if emp:
            empresa_nombre = emp.nombre_comercial or emp.razon_social or 'Empresa'
    except Exception:
        empresa_nombre = 'Empresa'

    root_id = '_root'
    root_node = {
        'id': root_id,
        'parentId': '',
        'name': empresa_nombre,
        'position': 'Empresa',
        'area': '',
        'subarea': '',
        'dni': '',
        'grupo': '',
        'email': '',
        'email_corp': '',
        'celular': '',
        'estado': 'Activo',
        'es_jefe': False,
        'nivel': 'GG',
        'personal_clave': False,
        '_isRoot': True,
    }
    for n in nodes:
        if not n['parentId']:
            n['parentId'] = root_id
    nodes.insert(0, root_node)

    # Ordenar: STAFF primero, luego RCO, luego otros (por parentId agrupado)
    def _sort_key(n):
        g = (n.get('grupo') or '').upper()
        if g == 'STAFF':
            return (0, n.get('name', ''))
        elif g == 'RCO':
            return (1, n.get('name', ''))
        return (2, n.get('name', ''))

    # Agrupar por parentId, ordenar dentro de cada grupo, reconstruir
    from collections import OrderedDict
    by_parent = OrderedDict()
    for n in nodes:
        pid = n['parentId']
        by_parent.setdefault(pid, []).append(n)
    sorted_nodes = []
    # Root node first (parentId='')
    for pid, children in by_parent.items():
        children.sort(key=_sort_key)
        sorted_nodes.extend(children)

    return JsonResponse(sorted_nodes, safe=False)


@login_required
@solo_admin
def organigrama_update_parent(request):
    """API para actualizar el campo reporta_a de un empleado (drag & drop o form)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST requerido'}, status=405)

    import json as _json
    try:
        data = _json.loads(request.body)
        personal_id = int(data['personal_id'])
        parent_id = data.get('parent_id')  # None para hacer raíz

        p = Personal.objects.get(id=personal_id)
        if parent_id:
            parent = Personal.objects.get(id=int(parent_id))
            # Evitar ciclos
            current = parent
            while current.reporta_a_id:
                if current.reporta_a_id == personal_id:
                    return JsonResponse({'error': 'Ciclo detectado'}, status=400)
                current = current.reporta_a
            p.reporta_a = parent
        else:
            p.reporta_a = None
        p.save(update_fields=['reporta_a'])
        return JsonResponse({'ok': True})
    except (Personal.DoesNotExist, KeyError, ValueError) as e:
        return JsonResponse({'error': str(e)}, status=400)


# ── Mapa de nivel_org → colores del organigrama (coincide con Excel) ──
NIVEL_COLORES = {
    'GG':      {'bg': '#FFC000', 'text': '#000000', 'border': '#D4A000', 'label': 'Gerente General'},
    'CTA':     {'bg': '#0070C0', 'text': '#FFFFFF', 'border': '#005A9E', 'label': 'Representante Cliente'},
    'DIR':     {'bg': '#1F3864', 'text': '#FFFFFF', 'border': '#162952', 'label': 'Director / Alta Gerencia'},
    'GER':     {'bg': '#7030A0', 'text': '#FFFFFF', 'border': '#5A2780', 'label': 'Gerente de Área'},
    'JEFE_SR': {'bg': '#2E5090', 'text': '#FFFFFF', 'border': '#1E3A6E', 'label': 'Jefe Senior'},
    'JEFE':    {'bg': '#4472C4', 'text': '#FFFFFF', 'border': '#2F5496', 'label': 'Jefe / Coordinador'},
    'ESP':     {'bg': '#F2F2F2', 'text': '#1F3864', 'border': '#BFBFBF', 'label': 'Especialista / Ingeniero'},
    'ASIST':   {'bg': '#FFFFFF', 'text': '#374151', 'border': '#D1D5DB', 'label': 'Asistente / Técnico'},
    'LIBERTY': {'bg': '#ED7D31', 'text': '#FFFFFF', 'border': '#C55A11', 'label': 'Liberty'},
    'EXPAT':   {'bg': '#FF69B4', 'text': '#FFFFFF', 'border': '#C71585', 'label': 'Expatriado'},
}


def _detectar_nivel_org(cargo: str) -> str:
    """Deriva nivel_org automáticamente del texto del cargo."""
    if not cargo:
        return 'ASIST'
    c = cargo.upper()
    if re.search(r'GERENTE GENERAL|DIRECTOR GENERAL|CEO|PRESIDENTE', c):
        return 'GG'
    if re.search(r'CTA|REPRESENTANTE.*CLIENTE|KP\b|CONTRATANTE', c):
        return 'CTA'
    if re.search(r'^DIRECTOR|DIRECTOR DE PROYECTO|RESIDENTE DE OBRA|GERENTE TECNICO.*CLIENTE', c):
        return 'DIR'
    if re.search(r'GERENTE|DIRECTOR', c):
        return 'GER'
    if re.search(r'JEFE.*SENIOR|SUBGERENTE|SUPERINTENDENTE|MANAGER|BIM MANAGER|COMMISSIONING MANAGER', c):
        return 'JEFE_SR'
    if re.search(r'\bJEFE\b|\bJEFA\b|COORDINADOR|COORDINADORA|RESPONSABLE|RESIDENTE(?! DE OBRA)', c):
        return 'JEFE'
    if re.search(r'ANALISTA|ESPECIALISTA|INGENIERO|ING\b|ARQ\b|ARQUITECTO|CONTADOR|ABOGADO|MEDICO|EXPERTO|SUPERVISOR|CAPATAZ', c):
        return 'ESP'
    return 'ASIST'


# ── Patrones de cargos jerárquicos ──
CARGO_NIVELES = [
    (1, re.compile(r'gerente\s*general|director\s*general|ceo|presidente', re.I)),
    (2, re.compile(r'gerente|director|vicepresidente|vp\b', re.I)),
    (3, re.compile(r'superintendente|sub\s*gerente|sub\s*director', re.I)),
    (4, re.compile(r'jefe|jefa|coordinador|coordinadora|responsable', re.I)),
    (5, re.compile(r'supervisor|supervisora|l[ií]der|encargado|encargada', re.I)),
    (6, re.compile(r'analista\s*senior|especialista\s*senior|ingeniero\s*senior', re.I)),
    (7, re.compile(r'analista|especialista|ingeniero|contador|abogado|m[eé]dico', re.I)),
    (8, re.compile(r'asistente|auxiliar|t[eé]cnico|operario|operador|obrero|practicante', re.I)),
]


def _detectar_nivel_cargo(cargo):
    """Detecta el nivel jerárquico de un cargo (1=más alto, 8=más bajo)."""
    if not cargo:
        return 9
    for nivel, patron in CARGO_NIVELES:
        if patron.search(cargo):
            return nivel
    return 9  # Sin clasificar


@login_required
@solo_admin
def organigrama_gestion(request):
    """Panel de gestión de jerarquía del organigrama."""
    areas = Area.objects.filter(activa=True).select_related('jefe_area').order_by('nombre')
    personal_activo = Personal.objects.filter(estado='Activo').select_related(
        'subarea__area', 'reporta_a'
    ).order_by('apellidos_nombres')

    # Estadísticas
    total = personal_activo.count()
    con_jefe = personal_activo.exclude(reporta_a=None).count()
    sin_jefe = total - con_jefe
    areas_sin_jefe = Area.objects.filter(activa=True, jefe_area=None).count()
    areas_total = Area.objects.filter(activa=True).count()

    # Análisis por área
    areas_info = []
    for area in areas:
        personal_area = personal_activo.filter(subarea__area=area)
        count = personal_area.count()
        con_reporta = personal_area.exclude(reporta_a=None).count()
        subareas = SubArea.objects.filter(area=area, activa=True).order_by('nombre')

        # Detectar posibles jefes por cargo
        posibles_jefes = []
        for p in personal_area:
            nivel = _detectar_nivel_cargo(p.cargo)
            if nivel <= 5:
                posibles_jefes.append({
                    'id': p.id,
                    'nombre': p.apellidos_nombres,
                    'cargo': p.cargo,
                    'nivel': nivel,
                })
        posibles_jefes.sort(key=lambda x: (x['nivel'], x['nombre']))

        areas_info.append({
            'area': area,
            'personal_count': count,
            'con_reporta': con_reporta,
            'sin_reporta': count - con_reporta,
            'subareas': subareas,
            'jefe_actual': area.jefe_area,
            'posibles_jefes': posibles_jefes[:5],
        })

    context = {
        'titulo': 'Gestión de Organigrama',
        'total': total,
        'con_jefe': con_jefe,
        'sin_jefe': sin_jefe,
        'pct_asignado': round(con_jefe / total * 100) if total else 0,
        'areas_sin_jefe': areas_sin_jefe,
        'areas_total': areas_total,
        'areas_info': areas_info,
        'personal_activo': personal_activo,
    }
    return render(request, 'personal/organigrama_gestion.html', context)


@login_required
@solo_admin
def organigrama_analizar(request):
    """API: Analiza la estructura y sugiere jerarquía automáticamente."""
    personal = Personal.objects.filter(estado='Activo').select_related(
        'subarea__area', 'reporta_a'
    )
    areas = Area.objects.filter(activa=True).select_related('jefe_area')

    resultados = {
        'areas_analizadas': 0,
        'jefes_detectados': 0,
        'sugerencias': [],
        'problemas': [],
    }

    for area in areas:
        resultados['areas_analizadas'] += 1
        personal_area = personal.filter(subarea__area=area)
        if not personal_area.exists():
            resultados['problemas'].append({
                'tipo': 'area_vacia',
                'mensaje': f'Área "{area.nombre}" no tiene personal activo asignado.',
                'area_id': area.id,
            })
            continue

        # Clasificar personal por nivel de cargo
        por_nivel = defaultdict(list)
        for p in personal_area:
            nivel = _detectar_nivel_cargo(p.cargo)
            por_nivel[nivel].append(p)

        # Encontrar el nivel más alto (número más bajo)
        niveles_presentes = sorted(por_nivel.keys())
        nivel_jefe = niveles_presentes[0] if niveles_presentes else 9

        # Sugerir jefe de área si no tiene
        if not area.jefe_area_id:
            candidatos = por_nivel[nivel_jefe]
            if candidatos:
                mejor = candidatos[0]
                resultados['sugerencias'].append({
                    'tipo': 'jefe_area',
                    'mensaje': f'Sugerir "{mejor.apellidos_nombres}" ({mejor.cargo}) como jefe de "{area.nombre}"',
                    'area_id': area.id,
                    'personal_id': mejor.id,
                    'nombre': mejor.apellidos_nombres,
                    'cargo': mejor.cargo,
                })
                resultados['jefes_detectados'] += 1
        else:
            resultados['jefes_detectados'] += 1

        # Sugerencias de reporta_a dentro del área
        jefe_area_id = area.jefe_area_id or (por_nivel[nivel_jefe][0].id if por_nivel[nivel_jefe] else None)

        for nivel in niveles_presentes:
            for p in por_nivel[nivel]:
                if p.reporta_a_id:
                    continue  # Ya tiene jefe asignado
                if p.id == jefe_area_id:
                    continue  # Es el jefe del área

                # Buscar supervisor: alguien del nivel inmediato superior en la misma área
                nivel_superior = None
                for n in sorted(por_nivel.keys()):
                    if n < nivel:
                        nivel_superior = n
                nivel_superior = nivel_superior or nivel_jefe

                if nivel_superior in por_nivel and por_nivel[nivel_superior]:
                    supervisor = por_nivel[nivel_superior][0]
                    if supervisor.id != p.id:
                        resultados['sugerencias'].append({
                            'tipo': 'reporta_a',
                            'mensaje': f'{p.apellidos_nombres} ({p.cargo}) → reporta a {supervisor.apellidos_nombres} ({supervisor.cargo})',
                            'personal_id': p.id,
                            'parent_id': supervisor.id,
                            'nombre': p.apellidos_nombres,
                            'parent_nombre': supervisor.apellidos_nombres,
                        })

    return JsonResponse(resultados)


@login_required
@solo_admin
@require_POST
def organigrama_auto_asignar(request):
    """
    Asigna jerarquía automáticamente basándose en áreas, cargos y niveles.
    Lógica:
    1. Para cada área, detectar el jefe (cargo más alto o jefe_area existente)
    2. Personal sin reporta_a → asignar al nivel superior más cercano en su área
    3. Jefes de área sin reporta_a → quedan como nodos raíz (reportan a gerencia general)
    """
    data = json.loads(request.body) if request.body else {}
    modo = data.get('modo', 'preview')  # 'preview' o 'aplicar'
    solo_vacios = data.get('solo_vacios', True)  # Solo asignar a quienes no tienen

    personal = Personal.objects.filter(estado='Activo').select_related('subarea__area')
    areas = Area.objects.filter(activa=True).select_related('jefe_area')

    cambios = []

    # Encontrar al Gerente General (nivel 1)
    gerente_general = None
    for p in personal:
        if _detectar_nivel_cargo(p.cargo) == 1:
            gerente_general = p
            break

    for area in areas:
        personal_area = list(personal.filter(subarea__area=area))
        if not personal_area:
            continue

        # Clasificar por nivel
        por_nivel = defaultdict(list)
        for p in personal_area:
            por_nivel[_detectar_nivel_cargo(p.cargo)].append(p)

        niveles = sorted(por_nivel.keys())
        if not niveles:
            continue

        # Determinar jefe del área
        jefe = area.jefe_area
        if not jefe and por_nivel[niveles[0]]:
            jefe = por_nivel[niveles[0]][0]
            # Sugerir asignar como jefe_area
            cambios.append({
                'tipo': 'jefe_area',
                'area_id': area.id,
                'area_nombre': area.nombre,
                'personal_id': jefe.id,
                'nombre': jefe.apellidos_nombres,
                'cargo': jefe.cargo,
            })

        if not jefe:
            continue

        # Jefe de área → reporta a Gerente General (si existe y es diferente)
        if gerente_general and jefe.id != gerente_general.id:
            if not jefe.reporta_a_id or not solo_vacios:
                if jefe.reporta_a_id != gerente_general.id:
                    cambios.append({
                        'tipo': 'reporta_a',
                        'personal_id': jefe.id,
                        'nombre': jefe.apellidos_nombres,
                        'cargo': jefe.cargo,
                        'parent_id': gerente_general.id,
                        'parent_nombre': gerente_general.apellidos_nombres,
                        'area': area.nombre,
                    })

        # Para cada nivel, asignar al nivel superior más cercano
        for i, nivel in enumerate(niveles):
            for p in por_nivel[nivel]:
                if p.id == jefe.id:
                    continue
                if solo_vacios and p.reporta_a_id:
                    continue

                # Buscar superior: nivel inmediato anterior, o el jefe
                supervisor = jefe
                for n in reversed(niveles[:i]):
                    if por_nivel[n]:
                        supervisor = por_nivel[n][0]
                        break

                if supervisor.id != p.id and p.reporta_a_id != supervisor.id:
                    cambios.append({
                        'tipo': 'reporta_a',
                        'personal_id': p.id,
                        'nombre': p.apellidos_nombres,
                        'cargo': p.cargo,
                        'parent_id': supervisor.id,
                        'parent_nombre': supervisor.apellidos_nombres,
                        'area': area.nombre,
                    })

    if modo == 'aplicar':
        aplicados = 0
        for c in cambios:
            if c['tipo'] == 'jefe_area':
                Area.objects.filter(id=c['area_id']).update(jefe_area_id=c['personal_id'])
                aplicados += 1
            elif c['tipo'] == 'reporta_a':
                Personal.objects.filter(id=c['personal_id']).update(reporta_a_id=c['parent_id'])
                aplicados += 1
        return JsonResponse({'ok': True, 'aplicados': aplicados, 'cambios': cambios})

    return JsonResponse({'ok': True, 'total_cambios': len(cambios), 'cambios': cambios})


@login_required
@solo_admin
@require_POST
def organigrama_asignar_jefe_area(request):
    """Asigna o cambia el jefe de un área."""
    data = json.loads(request.body)
    area_id = data.get('area_id')
    personal_id = data.get('personal_id')

    try:
        area = Area.objects.get(id=area_id)
        if personal_id:
            personal = Personal.objects.get(id=personal_id, estado='Activo')
            area.jefe_area = personal
        else:
            area.jefe_area = None
        area.save(update_fields=['jefe_area'])
        return JsonResponse({'ok': True})
    except (Area.DoesNotExist, Personal.DoesNotExist) as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@solo_admin
@require_POST
def organigrama_bulk_reporta(request):
    """Asigna reporta_a en lote."""
    data = json.loads(request.body)
    asignaciones = data.get('asignaciones', [])  # [{personal_id, parent_id}, ...]
    count = 0
    for a in asignaciones:
        try:
            pid = int(a['personal_id'])
            parent = int(a['parent_id']) if a.get('parent_id') else None
            if parent and parent == pid:
                continue
            Personal.objects.filter(id=pid).update(reporta_a_id=parent)
            count += 1
        except (ValueError, TypeError):
            continue
    return JsonResponse({'ok': True, 'actualizados': count})
