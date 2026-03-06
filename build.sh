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
python manage.py setup_harmoni --no-input 2>/dev/null || true

echo "=== Loading demo data ==="
python manage.py seed_demo_data 2>/dev/null || true

echo "=== Build complete ==="
