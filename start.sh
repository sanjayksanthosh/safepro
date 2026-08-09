#!/bin/sh
set -e

# Render/Fly set $PORT at runtime; default to 8000 if it's missing.
PORT="${PORT:-8000}"

mkdir -p /app/logs
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# 1 worker + multiple threads: the scraping job bookkeeping (job lock,
# live progress) lives in process memory, so the app must stay single-process.
exec gunicorn safepro_backend.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 8 \
    --timeout 180 \
    --access-logfile - \
    --error-logfile -
