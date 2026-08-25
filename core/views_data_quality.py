"""Centro de Saneamiento: convierte alertas de datos en trabajo resoluble."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.data_quality import build_data_quality_snapshot
from core.permisos import requiere_modulo_o_staff


@login_required
@requiere_modulo_o_staff('analytics')
def data_quality_center(request):
    cola = request.GET.get('cola', 'todos')
    if cola not in {'todos', 'empresa', 'legajos', 'liquidaciones', 'huerfanos'}:
        cola = 'todos'
    if cola == 'huerfanos' and not request.user.is_superuser:
        cola = 'todos'
    return render(request, 'core/data_quality.html', {
        'titulo': 'Centro de Saneamiento',
        'cola': cola,
        **build_data_quality_snapshot(request),
    })
