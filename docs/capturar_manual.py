"""
Captura automatizada de todas las pantallas de Harmoni para el manual.
Usa Playwright para navegar, login, y screenshot de cada modulo.
"""
import os
import time
import json
import traceback
from playwright.sync_api import sync_playwright

BASE = "https://harmoni.pe"
OUT = r"D:\Harmoni\docs\manual_capturas"
SHOTS = []

os.makedirs(OUT, exist_ok=True)

def ss(page, folder, name, title, desc, module, wait=2000, full=True, scroll_y=None):
    """Take screenshot."""
    os.makedirs(os.path.join(OUT, folder), exist_ok=True)
    path = os.path.join(OUT, folder, f"{name}.png")
    page.wait_for_timeout(wait)
    if scroll_y is not None:
        page.evaluate(f"window.scrollTo(0, {scroll_y})")
        page.wait_for_timeout(500)
    page.screenshot(path=path, full_page=full)
    SHOTS.append({'path': path, 'folder': folder, 'name': name, 'title': title, 'description': desc, 'module': module})
    print(f"  [OK] {folder}/{name} - {title}")

def goto(page, path, wait=2000):
    page.goto(f"{BASE}{path}")
    page.wait_for_timeout(wait)

def click_safe(page, sel, wait=1500, timeout=4000):
    try:
        page.click(sel, timeout=timeout)
        page.wait_for_timeout(wait)
        return True
    except Exception:
        return False

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1920, 'height': 1080}, locale='es-PE')
        page = ctx.new_page()

        # ===== LOGIN =====
        print("=== LOGIN ===")
        goto(page, '/login/')
        ss(page, "00_login", "01_login_page", "Pantalla de Inicio de Sesion",
           "Formulario de login con campos de usuario y contrasena. Diseno limpio con logo Harmoni, opciones de recuperar contrasena y selector de empresa.",
           "Login", full=False)

        page.locator('input[name="username"]').fill('admin')
        page.locator('input[name="password"]').fill('admin123')
        page.locator('button[type="submit"]').click()
        page.wait_for_timeout(3000)

        # ===== 01. DASHBOARD =====
        print("\n=== 01. DASHBOARD ===")
        goto(page, '/')
        ss(page, "01_dashboard", "01_main", "Dashboard Principal",
           "Vista principal con saludo personalizado, fecha, 200 colaboradores activos. Grafico donut Staff vs RCO. KPIs de asistencia: Presentes, Faltas, Permisos. Alerta de 57 contratos por vencer.",
           "Dashboard", full=False)

        ss(page, "01_dashboard", "02_accesos_rapidos", "Accesos Rapidos y Modulos",
           "Tarjetas de acceso rapido: Personal, Asistencia, Vacaciones, Nominas, Analytics, Aprobaciones, Roster, Prestamos, Documentos, Reclutamiento, Cierre, Importar. Seccion Portal del Trabajador con accesos a Mi Portal, Mi Asistencia, Mis Vacaciones, Mis Papeletas, Mis Bonos, Mis Eventos.",
           "Dashboard", full=True)

        # ===== 02. PERSONAL =====
        print("\n=== 02. PERSONAL ===")
        # Empleados
        goto(page, '/personal/')
        ss(page, "02_personal", "01_lista_empleados", "Lista de Empleados",
           "Tabla paginada de colaboradores con filtros por estado (activo/cesado), area, proyecto. Busqueda por nombre/DNI. Muestra foto, nombre, DNI, cargo, area, proyecto, condicion (Staff/RCO).",
           "Personal", full=False)

        # Detalle de un empleado
        try:
            links = page.locator('table tbody tr td a')
            if links.count() > 0:
                links.first.click()
                page.wait_for_timeout(2000)
                ss(page, "02_personal", "02_detalle_general", "Ficha de Empleado - Datos Generales",
                   "Ficha completa del trabajador: foto, datos personales (nombre, DNI, fecha nacimiento, direccion, email, telefono), informacion laboral (cargo, area, fecha ingreso, tipo contrato, regimen de turno, condicion).",
                   "Personal", full=False)
                ss(page, "02_personal", "03_detalle_scroll1", "Ficha de Empleado - Info Laboral y Contratos",
                   "Seccion media: historial de contratos con tipo, fechas, estado. Datos bancarios, informacion tributaria (AFP/ONP), asignacion familiar, regimen de turno.",
                   "Personal", full=True)
                page.go_back()
                page.wait_for_timeout(1000)
        except Exception:
            print("  [WARN] Could not open employee detail")

        # Areas
        goto(page, '/personal/areas/')
        ss(page, "02_personal", "04_areas", "Areas y Gerencias",
           "Estructura organizacional de la empresa: areas funcionales con gerente responsable y conteo de empleados por area.",
           "Personal", full=False)

        # SubAreas
        goto(page, '/personal/subareas/')
        ss(page, "02_personal", "05_subareas", "Sub-Areas",
           "Desglose de sub-areas dentro de cada gerencia/area. Permite organizar el personal en unidades mas especificas.",
           "Personal", full=False)

        # Organigrama
        goto(page, '/personal/organigrama/', wait=4000)
        ss(page, "02_personal", "06_organigrama", "Organigrama Corporativo",
           "Organigrama interactivo de la empresa con niveles jerarquicos. Colores por area: Gerencia General (esmeralda), Administracion (azul), Operaciones (naranja). Drill-down por nodos, zoom, export.",
           "Personal", full=False)

        # Roster
        goto(page, '/personal/roster/')
        ss(page, "02_personal", "07_roster", "Roster Matricial",
           "Vista matricial del personal por proyecto con calendario de asignaciones, dias trabajados, descansos y vacaciones programadas.",
           "Personal", full=False)

        # Calendario Laboral
        goto(page, '/personal/calendario/')
        ss(page, "02_personal", "08_calendario_laboral", "Calendario Laboral",
           "Calendario con feriados nacionales peruanos, dias no laborables por empresa, eventos corporativos y fechas clave del periodo.",
           "Personal", full=False)

        # Contratos
        goto(page, '/personal/contratos/')
        ss(page, "02_personal", "09_contratos", "Gestion de Contratos",
           "Lista de contratos laborales: tipo (plazo fijo, indeterminado, obra), fechas inicio/fin, estado (vigente/vencido/por vencer). Alertas de vencimiento. Generacion de PDF/DOCX.",
           "Personal", full=False)

        # Detalle de un contrato
        try:
            links = page.locator('table tbody tr td a')
            if links.count() > 0:
                links.first.click()
                page.wait_for_timeout(2000)
                ss(page, "02_personal", "10_contrato_detalle", "Detalle de Contrato",
                   "Vista completa de un contrato: datos del trabajador, tipo de contrato, clausulas, fechas, prorrogas. Botones para generar PDF, DOCX, prorroga, adenda (aumento salarial, cambio de cargo, cambio de condiciones).",
                   "Personal", full=True)
                page.go_back()
                page.wait_for_timeout(1000)
        except Exception:
            print("  [WARN] Could not open contract detail")

        # Reportes RRHH
        goto(page, '/personal/reportes/')
        ss(page, "02_personal", "11_reportes", "Reportes de RRHH",
           "Centro de reportes: headcount, rotacion de personal, antiguedad, contratos por vencer, altas y bajas del periodo, distribucion por area/cargo.",
           "Personal", full=False)

        # ===== 03. ASISTENCIA =====
        print("\n=== 03. ASISTENCIA ===")
        goto(page, '/asistencia/')
        ss(page, "03_asistencia", "01_dashboard", "Dashboard de Asistencia",
           "Panel de control de asistencia: resumen del dia, contadores de presentes/faltas/tardanzas/permisos. Graficos de tendencia diaria. Acceso rapido a importar tareo.",
           "Asistencia", full=False)

        # Vista Unificada
        goto(page, '/asistencia/vista-unificada/')
        ss(page, "03_asistencia", "02_vista_unificada", "Vista Unificada de Asistencia",
           "Vista consolidada de todos los registros por fecha: marca ingreso, marca salida, horas trabajadas, horas extra, tipo de dia (normal, feriado, descanso). Filtros por area, proyecto, trabajador.",
           "Asistencia", full=False)

        # Calendario Grid marzo 2026
        goto(page, '/asistencia/calendario/?mes=2026-03', wait=3000)
        ss(page, "03_asistencia", "03_calendario_marzo", "Calendario de Asistencia - Marzo 2026",
           "Grilla tipo calendario con asistencia diaria por empleado. Colores semaforizados: verde=presente, rojo=falta, amarillo=permiso, azul=vacaciones, gris=descanso, morado=feriado. Vista mensual completa.",
           "Asistencia", full=True)

        # Importar
        goto(page, '/asistencia/importar/')
        ss(page, "03_asistencia", "04_importar", "Importar Tareo / Biometrico",
           "Modulo de importacion de registros de asistencia desde multiples fuentes: Excel S10, biometrico, importacion manual. Soporte para formatos detalle y resumen.",
           "Asistencia", full=False)

        # Papeletas
        goto(page, '/asistencia/papeletas/')
        ss(page, "03_asistencia", "05_papeletas", "Gestion de Papeletas",
           "Lista de papeletas de permiso: salida anticipada, permiso personal, comision de servicio, licencia. Estados: Pendiente, Aprobada, Ejecutada. Flujo de aprobacion configurable.",
           "Asistencia", full=False)

        # Banco de Horas
        goto(page, '/asistencia/banco-horas/')
        ss(page, "03_asistencia", "06_banco_horas", "Banco de Horas Extra",
           "Control de horas extra acumuladas: saldo disponible, movimientos de carga/compensacion, historial. Permite acumular HE para uso posterior como descanso compensatorio.",
           "Asistencia", full=False)

        # Reporte Staff marzo
        goto(page, '/asistencia/reporte-staff/?mes=2026-03')
        ss(page, "03_asistencia", "07_reporte_staff", "Reporte de Asistencia Staff - Marzo 2026",
           "Reporte detallado para personal Staff: dias trabajados, horas normales, horas extra (25%, 35%, 100%), horas nocturnas, descansos semanales, feriados, faltas, permisos, vacaciones. Exportable a Excel.",
           "Asistencia", full=True)

        # Reporte RCO
        goto(page, '/asistencia/reporte-rco/?mes=2026-03')
        ss(page, "03_asistencia", "08_reporte_rco", "Reporte de Asistencia RCO - Marzo 2026",
           "Reporte especifico para personal de Regimen Civil de Obra: jornada especial, control de condicion foranea/local, horas por turno, descanso semanal en dia distinto a domingo.",
           "Asistencia", full=True)

        # ===== 04. NOMINAS =====
        print("\n=== 04. NOMINAS ===")
        goto(page, '/nominas/')
        ss(page, "04_nominas", "01_periodos", "Periodos de Nomina",
           "Lista de periodos de nomina: mensual. Estado de cada periodo (abierto/cerrado/en proceso). Fechas de corte y pago. Botones para generar, cerrar y exportar.",
           "Nominas", full=False)

        # Ver si hay periodos
        try:
            link = page.locator('table tbody tr:first-child a').first
            link.click()
            page.wait_for_timeout(2000)
            ss(page, "04_nominas", "02_periodo_detalle", "Detalle de Periodo de Nomina",
               "Resumen del periodo: total bruto, total descuentos, neto a pagar. Conceptos remunerativos (basico, asignacion familiar, horas extra, gratificacion) y deductivos (AFP/ONP, IR 5ta, prestamos).",
               "Nominas", full=False)
            ss(page, "04_nominas", "03_periodo_tabla", "Tabla de Nomina por Empleado",
               "Tabla detallada empleado por empleado: sueldo basico, asignacion familiar, horas extra, gratificacion trunca, AFP/ONP, IR 5ta, prestamos, adelantos, neto a pagar. Totales en pie de tabla.",
               "Nominas", full=True)
            page.go_back()
            page.wait_for_timeout(1000)
        except Exception:
            print("  [WARN] No periods available")

        # Boletas
        goto(page, '/nominas/boletas/')
        ss(page, "04_nominas", "04_boletas", "Boletas de Pago",
           "Generacion y envio de boletas de pago en PDF. Individual o masivo. Formato oficial con todos los conceptos remunerativos y deductivos del periodo.",
           "Nominas", full=False)

        # ===== 05. VACACIONES =====
        print("\n=== 05. VACACIONES ===")
        goto(page, '/vacaciones/')
        ss(page, "05_vacaciones", "01_panel", "Panel de Vacaciones",
           "Vista general de vacaciones del equipo: saldos consolidados, solicitudes pendientes de aprobacion, calendario de vacaciones programadas.",
           "Vacaciones", full=False)

        goto(page, '/vacaciones/', wait=1000)
        ss(page, "05_vacaciones", "02_saldos", "Tabla de Saldos de Vacaciones",
           "Saldos por trabajador: dias ganados segun DL 713 (30d/ano), dias gozados, saldo pendiente, dias truncos, vacaciones vencidas. Filtros por estado y area.",
           "Vacaciones", full=True)

        # ===== 06. RECLUTAMIENTO =====
        print("\n=== 06. RECLUTAMIENTO ===")
        goto(page, '/reclutamiento/')
        ss(page, "06_reclutamiento", "01_vacantes", "Gestion de Vacantes",
           "Panel de reclutamiento: vacantes abiertas, en proceso, cerradas. Datos de cada vacante: cargo, area, requisitos, fecha publicacion, candidatos.",
           "Reclutamiento", full=False)

        # Crear vacante
        goto(page, '/reclutamiento/vacantes/crear/')
        ss(page, "06_reclutamiento", "02_crear_vacante", "Crear Nueva Vacante",
           "Formulario para crear vacante: cargo, area, tipo de contrato, rango salarial, requisitos, funciones, fecha limite. Publicacion en portal interno.",
           "Reclutamiento", full=True)

        # ===== 07. ONBOARDING =====
        print("\n=== 07. ONBOARDING ===")
        goto(page, '/onboarding/')
        ss(page, "07_onboarding", "01_panel", "Panel de Onboarding",
           "Gestion de incorporacion de nuevos colaboradores: checklist de documentos requeridos, proceso de induccion, asignacion de equipos/recursos, firma de contrato.",
           "Onboarding", full=False)

        # ===== 08. WORKFLOWS =====
        print("\n=== 08. WORKFLOWS ===")
        goto(page, '/workflows/')
        ss(page, "08_workflows", "01_aprobaciones", "Centro de Aprobaciones",
           "Flujos de aprobacion centralizados: vacaciones, permisos, prestamos, gastos de viaje. Visualizacion de estado: pendiente, aprobado, rechazado. Escalamiento automatico por tiempo.",
           "Workflows", full=False)

        # ===== 09. DOCUMENTOS =====
        print("\n=== 09. DOCUMENTOS ===")
        goto(page, '/documentos/')
        ss(page, "09_documentos", "01_panel", "Gestion Documental",
           "Repositorio centralizado de documentos por empleado: contratos firmados, DNI/CE, certificados, constancias, memorandums. Categorias, fechas de vencimiento, descarga.",
           "Documentos", full=False)

        # ===== 10. COMUNICACIONES =====
        print("\n=== 10. COMUNICACIONES ===")
        goto(page, '/comunicaciones/')
        ss(page, "10_comunicaciones", "01_panel", "Comunicaciones Internas",
           "Sistema de comunicaciones: anuncios generales, circulares por area, memorandums individuales, notificaciones push. Historial de envios y lectura.",
           "Comunicaciones", full=False)

        # ===== 11. ANALYTICS =====
        print("\n=== 11. ANALYTICS ===")
        goto(page, '/analytics/', wait=4000)
        ss(page, "11_analytics", "01_dashboard", "Dashboard de Analytics",
           "Metricas avanzadas de RRHH: headcount por area, evolucion mensual, indice de rotacion, costo laboral, distribucion por cargo y antiguedad. Graficos interactivos con Chart.js.",
           "Analytics", full=False)
        ss(page, "11_analytics", "02_graficos", "Analytics - Graficos Detallados",
           "Graficos de tendencias: altas vs bajas, evolucion de headcount, distribucion de genero, piramide de edades, top cargos. Exportable a Excel e imagen.",
           "Analytics", full=True)

        # ===== 12. PRESTAMOS =====
        print("\n=== 12. PRESTAMOS ===")
        goto(page, '/prestamos/')
        ss(page, "12_prestamos", "01_panel", "Gestion de Prestamos",
           "Control de prestamos a empleados: monto, numero de cuotas, tasa de interes, estado de pago. Descuento automatico en nomina. Simulador de cuotas.",
           "Prestamos", full=False)

        # ===== 13. INTEGRACIONES =====
        print("\n=== 13. INTEGRACIONES ===")
        goto(page, '/integraciones/')
        ss(page, "13_integraciones", "01_panel", "Integraciones y Exportaciones",
           "Centro de exportaciones a entidades oficiales: PLAME (SUNAT), PDT, T-Registro, AFP Net, CTS bancos (Telecredito BCP, BBVA). Formatos oficiales vigentes.",
           "Integraciones", full=False)

        # ===== 14. CIERRE =====
        print("\n=== 14. CIERRE ===")
        goto(page, '/cierre/')
        ss(page, "14_cierre", "01_panel", "Cierre Mensual",
           "Proceso de cierre de periodo: validaciones previas (contratos, asistencia, nomina), consolidacion de datos, generacion de reportes finales, bloqueo de edicion retroactiva.",
           "Cierre", full=False)

        # ===== 15. PORTAL DEL TRABAJADOR =====
        print("\n=== 15. PORTAL ===")
        goto(page, '/mi-portal/')
        ss(page, "15_portal", "01_portal_main", "Portal del Trabajador",
           "Vista del empleado (autoservicio): mis datos personales, boletas de pago, mis vacaciones, documentos, solicitudes de permiso/vacaciones, comunicaciones. Acceso con credenciales individuales.",
           "Portal", full=False)

        # ===== 16. CALENDARIO =====
        print("\n=== 16. CALENDARIO ===")
        goto(page, '/calendario/')
        ss(page, "16_calendario", "01_calendario", "Calendario Corporativo",
           "Calendario centralizado de la empresa: feriados nacionales, vacaciones del equipo, cumpleanos, vencimientos de contratos, eventos de capacitacion.",
           "Calendario", full=False)

        # ===== 17. CAPACITACIONES =====
        print("\n=== 17. CAPACITACIONES ===")
        goto(page, '/capacitaciones/')
        ss(page, "17_capacitaciones", "01_panel", "Gestion de Capacitaciones",
           "Plan anual de capacitaciones: cursos, talleres, certificaciones. Control de asistencia, evaluaciones, certificados. Presupuesto asignado y ejecutado.",
           "Capacitaciones", full=False)

        # ===== 18. EVALUACIONES =====
        print("\n=== 18. EVALUACIONES ===")
        goto(page, '/evaluaciones/')
        ss(page, "18_evaluaciones", "01_panel", "Evaluaciones de Desempeno",
           "Sistema de evaluaciones: objetivos (OKR), competencias, evaluacion 360. Ciclos de evaluacion configurables, retroalimentacion, planes de mejora.",
           "Evaluaciones", full=False)

        # ===== 19. DISCIPLINARIA =====
        print("\n=== 19. DISCIPLINARIA ===")
        goto(page, '/disciplinaria/')
        ss(page, "19_disciplinaria", "01_panel", "Gestion Disciplinaria",
           "Registro de medidas disciplinarias: amonestaciones verbales, escritas, suspensiones, despido. Historial por trabajador, base legal, fechas.",
           "Disciplinaria", full=False)

        # ===== 20. ENCUESTAS =====
        print("\n=== 20. ENCUESTAS ===")
        goto(page, '/encuestas/')
        ss(page, "20_encuestas", "01_panel", "Encuestas de Clima",
           "Encuestas de clima laboral y satisfaccion: creacion de formularios, envio masivo, seguimiento de respuestas, resultados graficos.",
           "Encuestas", full=False)

        # ===== 21. VIATICOS =====
        print("\n=== 21. VIATICOS ===")
        goto(page, '/viaticos/')
        ss(page, "21_viaticos", "01_panel", "Gestion de Viaticos",
           "Control de gastos de viaje: solicitudes, rendiciones, liquidaciones. Flujo de aprobacion, limites por cargo, integracion con nomina.",
           "Viaticos", full=False)

        # ===== 22. SALARIOS =====
        print("\n=== 22. SALARIOS ===")
        goto(page, '/salarios/')
        ss(page, "22_salarios", "01_panel", "Estructura Salarial",
           "Bandas salariales por cargo/nivel, historico de incrementos, simulador de aumentos, analisis de equidad interna.",
           "Salarios", full=False)

        # ===== 23. EMPRESAS =====
        print("\n=== 23. EMPRESAS ===")
        goto(page, '/empresas/')
        ss(page, "23_empresas", "01_panel", "Configuracion de Empresa",
           "Datos de la empresa: razon social, RUC, representante legal, logo, firma. Configuracion SMTP por empresa. Multi-tenant.",
           "Empresas", full=False)

        # ===== 24. SISTEMA / CORE =====
        print("\n=== 24. SISTEMA ===")
        goto(page, '/sistema/')
        ss(page, "24_sistema", "01_panel", "Configuracion del Sistema",
           "Administracion del sistema: parametros generales, configuracion de ciclo de nomina, feriados, tipos de horario, regimenes de turno, base de conocimiento IA.",
           "Sistema", full=False)

        # ===== LANDING PAGE =====
        print("\n=== LANDING PAGE ===")
        # Logout first, then capture landing
        goto(page, '/logout/')
        page.wait_for_timeout(1000)
        goto(page, '/')
        ss(page, "25_landing", "01_landing_hero", "Landing Page - Hero",
           "Pagina de inicio publica de Harmoni: ERP de RRHH que tu empresa necesita. Diseno glassmorphism con gradientes, animaciones. CTA: Solicitar Demo.",
           "Landing", full=False)
        ss(page, "25_landing", "02_landing_full", "Landing Page - Completa",
           "Landing page completa: hero, modulos del sistema, beneficios, precios (Starter S/149, Profesional S/349, Enterprise), formulario de contacto.",
           "Landing", full=True)

        # ===== SAVE METADATA =====
        meta = os.path.join(OUT, "screenshots_metadata.json")
        with open(meta, 'w', encoding='utf-8') as f:
            json.dump(SHOTS, f, ensure_ascii=False, indent=2, default=str)

        print(f"\n{'='*60}")
        print(f"TOTAL CAPTURAS: {len(SHOTS)}")
        print(f"Metadata: {meta}")
        print(f"{'='*60}")

        browser.close()

if __name__ == '__main__':
    main()
