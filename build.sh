#!/usr/bin/env bash
# Build script for Render deployment
set -o errexit

echo "=== Installing dependencies ==="
pip install -r requirements.txt

echo "=== Collecting static files ==="
python manage.py collectstatic --no-input

echo "=== Running migrations ==="
python manage.py migrate --noinput

echo "=== Creating cache table ==="
python manage.py createcachetable 2>/dev/null || true

echo "=== Running initial setup ==="
python manage.py setup_harmoni --no-input || true

echo "=== Loading employees fixture (280 real employees) ==="
python manage.py loaddata core/fixtures/empleados.json || true

echo "=== Loading modules fixture (vacaciones, caps, prestamos, etc) ==="
python manage.py loaddata core/fixtures/modulos_demo.json || true

echo "=== Build complete ==="
