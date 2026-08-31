# ReuseHub backend image — gunicorn serving the Django REST API.
# Runnable directly (single process) or via docker-compose (with PostgreSQL).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: psycopg2-binary ships its own libpq, so only minimal packages.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (layer caching benefits).
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Application code. requirements.txt excludes ruff/pytest from the runtime
# layer where practical; they are dev-only and pinged out by the build.
COPY . .

# Non-root runtime user.
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# The APP_PORT env allows compose/VPS to keep the interface without hardcoding.
CMD ["sh", "-c", "python manage.py migrate --noinput && \
    python manage.py collectstatic --noinput && \
    gunicorn config.wsgi:application --bind 0.0.0.0:${APP_PORT:-8000} \
        --workers ${WEB_CONCURRENCY:-2} --timeout 60"]