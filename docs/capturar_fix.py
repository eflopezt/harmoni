"""Re-capture pages that had wrong URLs + additional detail pages."""
import os, json
from playwright.sync_api import sync_playwright

BASE = "https://harmoni.pe"
OUT = r"D:\Harmoni\docs\manual_capturas"
SHOTS = []

# Load existing metadata
meta_path = os.path.join(OUT, "screenshots_metadata.json")
if os.path.exists(meta_path):
    with open(meta_path, 'r', encoding='utf-8') as f:
        SHOTS = json.load(f)

def ss(page, folder, name, title, desc, module, wait=2000, full=True):
    os.makedirs(os.path.join(OUT, folder), exist_ok=True)
    path = os.path.join(OUT, folder, f"{name}.png")
    page.wait_for_timeout(wait)
    page.screenshot(path=path, full_page=full)
    # Remove old entry if exists
    global SHOTS
    SHOTS = [s for s in SHOTS if s['name'] != name]
    SHOTS.append({'path': path, 'folder': folder, 'name': name, 'title': title, 'description': desc, 'module': module})
    print(f"  [OK] {folder}/{name} - {title}")

def goto(page, path, wait=2000):
    page.goto(f"{BASE}{path}")
    page.wait_for_timeout(wait)

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1920, 'height': 1080}, locale='es-PE')
        page = ctx.new_page()

        # Login
        goto(page, '/login/')
        page.locator('input[name="username"]').fill('admin')
        page.locator('input[name="password"]').fill('admin123')
        page.locator('button[type="submit"]').click()
        page.wait_for_timeout(3000)
        print("Logged in\n")

        # === FIX: Organigrama ===
        print("=== FIXES ===")
        goto(page, '/organigrama/', wait=4000)
        ss(page, "02_personal", "06_organigrama", "Organigrama Corporativo",
           "Organigrama interactivo de la empresa con estructura jerarquica. Nodos coloreados por area (Gerencia General, Administracion, Operaciones, RRHH). Expandible con drill-down, zoom y exportacion.",
           "Personal", full=False)

        # FIX: Roster Matricial
        goto(page, '/roster/matricial/')
        ss(page, "02_personal", "07_roster", "Roster Matricial",
           "Vista matricial del personal asignado a proyectos: dias de trabajo, descansos programados, vacaciones, rotaciones. Planificacion visual tipo Gantt por semana/mes.",
           "Personal", full=False)

        # FIX: Reportes
        goto(page, '/reportes/')
        ss(page, "02_personal", "11_reportes", "Reportes de RRHH",
           "Centro de reportes de recursos humanos: headcount por area, rotacion de personal, antiguedad promedio, contratos por vencer, altas y bajas mensuales, distribucion por tipo contrato.",
           "Personal", full=False)

        # FIX: Reporte Staff
        goto(page, '/asistencia/staff/?mes=2026-03')
        ss(page, "03_asistencia", "07_reporte_staff", "Reporte de Asistencia Staff - Marzo 2026",
           "Reporte detallado para personal administrativo (Staff): dias efectivos, horas normales, horas extra 25%/35%/100%, horas nocturnas, domingos/feriados, descanso semanal, faltas, tardanzas, permisos, vacaciones. Exportable a Excel para integracion con S10.",
           "Asistencia", full=True)

        # FIX: Reporte RCO
        goto(page, '/asistencia/rco/?mes=2026-03')
        ss(page, "03_asistencia", "08_reporte_rco", "Reporte de Asistencia RCO - Marzo 2026",
           "Reporte especifico para Regimen Civil de Obra: jornada de 10h (foraneos), 8.5h (locales), control de condicion foranea/local, descanso semanal en dia diferente a domingo, reglas especiales por personal. Exportable a Excel.",
           "Asistencia", full=True)

        # FIX: Contrato detalle
        goto(page, '/personal/contratos/')
        try:
            page.locator('table tbody tr:first-child a').first.click()
            page.wait_for_timeout(2000)
            ss(page, "02_personal", "10_contrato_detalle", "Detalle de Contrato Laboral",
               "Vista completa de contrato: datos del empleador y trabajador, tipo (Obra Determinada, Confianza, Fiscalizable), clausulas segun DL 728. Botones: Generar PDF, Descargar DOCX, Prorroga, Adenda (aumento salarial, cambio cargo, cambio condiciones). Historial de prorrogas y adendas.",
               "Personal", full=True)
        except Exception:
            print("  [WARN] No contract detail")

        # === ADDITIONAL PAGES ===
        print("\n=== ADDITIONAL PAGES ===")

        # Nuevo Empleado form
        goto(page, '/personal/nuevo/')
        ss(page, "02_personal", "12_nuevo_empleado", "Formulario Nuevo Empleado",
           "Formulario de alta de nuevo colaborador: datos personales (nombres, DNI, fecha nacimiento, direccion, telefono, email), datos laborales (cargo, area, proyecto, fecha ingreso, tipo contrato, sueldo), datos tributarios (AFP/ONP, banco, cuenta).",
           "Personal", full=True)

        # Asistencia - detalle empleado
        goto(page, '/asistencia/calendario/?mes=2026-03')
        page.wait_for_timeout(2000)
        # Scroll to show data
        page.evaluate("window.scrollTo(0, 200)")
        ss(page, "03_asistencia", "03b_calendario_scroll", "Calendario Asistencia - Detalle Empleados",
           "Grilla de asistencia mes completo: cada celda muestra estado del dia (NOR=Normal, VAC=Vacaciones, DSE=Descanso Semanal, FER=Feriado, LCG=Licencia, SS=Sin Salida, AUS=Ausencia). Totales por columna y fila.",
           "Asistencia", full=False)

        # Nominas - boletas download
        goto(page, '/nominas/mis-recibos/')
        ss(page, "04_nominas", "05_mis_recibos", "Mis Recibos de Pago",
           "Vista de recibos/boletas de pago del trabajador actual: listado por periodo con descarga individual en PDF. Muestra todos los conceptos remunerativos y deductivos.",
           "Nominas", full=False)

        # Vacaciones - detalle saldos
        goto(page, '/vacaciones/saldos/')
        ss(page, "05_vacaciones", "03_saldos_detalle", "Detalle de Saldos de Vacaciones",
           "Tabla de saldos por trabajador: dias ganados (DL 713: 30d/ano), dias gozados, saldo pendiente, dias truncos, vacaciones vencidas (triple vacacional Art.23). Filtros por estado, area, proyecto.",
           "Vacaciones", full=True)

        # Portal items
        goto(page, '/mi-portal/')
        ss(page, "15_portal", "01_portal_main", "Portal del Trabajador - Inicio",
           "Dashboard del trabajador: accesos rapidos a mis datos, boletas, vacaciones, papeletas, documentos, comunicaciones. Resumen personalizado.",
           "Portal", full=False)

        goto(page, '/mi-portal/mis-datos/')
        ss(page, "15_portal", "02_mis_datos", "Portal - Mis Datos Personales",
           "Vista de datos personales del empleado: nombre, DNI, direccion, telefono, email, foto. El trabajador puede solicitar actualizacion de datos.",
           "Portal", full=False)

        goto(page, '/mi-portal/mi-asistencia/')
        ss(page, "15_portal", "03_mi_asistencia", "Portal - Mi Asistencia",
           "Vista de marcaciones de asistencia del trabajador: hora ingreso, hora salida, horas trabajadas, faltas, tardanzas. Calendario mensual personal.",
           "Portal", full=False)

        goto(page, '/mi-portal/mis-vacaciones/')
        ss(page, "15_portal", "04_mis_vacaciones", "Portal - Mis Vacaciones",
           "Vista del saldo de vacaciones del trabajador: dias ganados, gozados, pendientes. Solicitud de vacaciones con calendario y flujo de aprobacion.",
           "Portal", full=False)

        goto(page, '/mi-portal/mis-papeletas/')
        ss(page, "15_portal", "05_mis_papeletas", "Portal - Mis Papeletas",
           "Gestion de papeletas del trabajador: crear solicitud de permiso, ver estado (pendiente/aprobada/rechazada), historial de papeletas.",
           "Portal", full=False)

        # Integraciones detalle
        goto(page, '/integraciones/')
        ss(page, "13_integraciones", "01_panel", "Centro de Integraciones",
           "Exportaciones oficiales: PLAME mensual (SUNAT), T-Registro altas/bajas, AFP Net (aportes previsionales), CTS bancos (BCP Telecredito, BBVA Continental, Interbank), PDT 601. Cada exportacion genera archivo en formato oficial.",
           "Integraciones", full=True)

        # Configuracion empresa
        goto(page, '/empresas/')
        ss(page, "23_empresas", "01_panel", "Configuracion Multi-Empresa",
           "Datos de la empresa: razon social, RUC, direccion, representante legal (tipo doc, numero). Logo y firma digital para documentos. Configuracion SMTP por empresa (Gmail, Office 365, custom). Row-level tenancy multi-tenant.",
           "Empresas", full=True)

        # Save metadata
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(SHOTS, f, ensure_ascii=False, indent=2, default=str)

        print(f"\nTOTAL CAPTURAS ACTUALIZADAS: {len(SHOTS)}")
        browser.close()

if __name__ == '__main__':
    main()
