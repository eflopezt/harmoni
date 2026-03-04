@echo off
chcp 65001 >nul
title Harmoni ERP — Demo

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║         HARMONI ERP — Inicio Demo        ║
echo  ╚══════════════════════════════════════════╝
echo.

:: ── Detectar Python del venv ──────────────────────────────────────────────
set PYTHON=%~dp0.venv\Scripts\python.exe
if not exist "%PYTHON%" (
    echo  [ERROR] No se encontro el entorno virtual en .venv\
    echo  Ejecuta primero: python -m venv .venv ^& .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

:: ── Variables de entorno para desarrollo/demo ─────────────────────────────
set DJANGO_SETTINGS_MODULE=config.settings.development
set DJANGO_SECRET_KEY=demo-secret-key-harmoni-2026-presentacion
set DATABASE_URL=

echo  [1/4] Verificando migraciones...
"%PYTHON%" manage.py migrate --noinput 2>nul
if %errorlevel% neq 0 (
    echo  [ERROR] Fallo en migraciones. Revisa la consola.
    pause
    exit /b 1
)
echo  OK

echo  [2/4] Setup inicial (seeds + superusuario)...
"%PYTHON%" manage.py setup_harmoni --no-input 2>nul
echo  OK

echo  [3/4] Setup datos de demo...
"%PYTHON%" manage.py seed_demo_presentacion 2>nul
if %errorlevel% neq 0 (
    echo  [AVISO] seed_demo_presentacion omitido ^(puede que ya existan datos^)
)
echo  OK

:: ── Detectar IP local para que el cliente se conecte ─────────────────────
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4" ^| findstr /v "169.254"') do (
    set LOCAL_IP=%%a
    goto :got_ip
)
:got_ip
set LOCAL_IP=%LOCAL_IP: =%

echo.
echo  [4/4] Iniciando servidor...
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║  Sistema listo. Accede desde cualquier PC en la red: ║
echo  ║                                                      ║
echo  ║   Local:    http://127.0.0.1:8000                    ║
echo  ║   Red LAN:  http://%LOCAL_IP%:8000                  ║
echo  ║                                                      ║
echo  ║   Usuario: admin                                     ║
echo  ║   Clave:   Harmoni2026!                              ║
echo  ║                                                      ║
echo  ║   [Ctrl+C] para detener el servidor                  ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

"%PYTHON%" manage.py runserver 0.0.0.0:8000

pause
