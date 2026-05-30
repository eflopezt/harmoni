FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies (build + cairo for xhtml2pdf + mupdf + unixodbc-dev for pyodbc)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    pkg-config \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf-2.0-dev \
    libffi-dev \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (production only)
COPY requirements/ requirements/
RUN pip install --upgrade pip && \
    pip install -r requirements/production.txt

# --- Runtime stage ---
FROM python:3.12-slim

# TZ=America/Lima: el contenedor corre en UTC por defecto, lo que hacía que
# date.today()/datetime.now() (hora local del SO) devolvieran la fecha UTC —
# un día adelantada en las tardes/noches peruanas. Fijar la TZ del contenedor
# lo corrige a nivel de infraestructura.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=America/Lima

WORKDIR /app

# Runtime system deps only (no build tools)
# msodbcsql18 + unixodbc para conectar a SQL Server (integración Synkro RRHH)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq5 \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    tzdata \
    curl gnupg ca-certificates apt-transport-https \
    && ln -fs /usr/share/zoneinfo/America/Lima /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/microsoft-archive-keyring.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy project
COPY . .

# Create necessary directories
RUN mkdir -p staticfiles media logs

# Collect static files
RUN DJANGO_SECRET_KEY=build-placeholder \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    DATABASE_URL=sqlite:///tmp/build.db \
    python manage.py collectstatic --noinput 2>/dev/null; exit 0

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
