#!/usr/bin/env bash
# Render start command for the ReuseHub backend.
#
# Runs migrations, collects static files (WhiteNoise serves them), then starts
# gunicorn on the port Render provides (default 10000, overridable via PORT).
#
# --timeout 90 is above the ClickPesa USSD-initiation timeout (45s) so the
# gateway has time to respond without gunicorn killing the worker.
set -euo pipefail

python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:${PORT:-10000} \
    --workers ${WEB_CONCURRENCY:-2} \
    --timeout 90 \
    --access-logfile - \
    --error-logfile -
