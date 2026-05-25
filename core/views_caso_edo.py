"""
Landing comercial — caso de uso Grupo Sabores.

URL: /casos/edo/  (público, sin login)

Para enviar como link previo al meeting con Isabel. Cuenta la historia:
problema actual → solución Harmoni → ROI esperado → CTA demo.
"""
from django.shortcuts import render


def caso_edo(request):
    return render(request, 'casos/edo.html', {})
