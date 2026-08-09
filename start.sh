#!/bin/sh
set -e

# Render/Fly set $PORT at runtime; default to 8000 if it's missing.
PORT="${PORT:-8000}"

mkdir -p /app/logs

# First boot on a fresh (ephemeral) disk: seed from the bundled cache so
# common search terms return instantly. Refresh timestamps so they count
# as fresh for CACHE_HOURS.
if [ ! -f /app/db.sqlite3 ] && [ -f /app/seed.sqlite3 ]; then
  echo "Seeding database from bundled cache..."
  cp /app/seed.sqlite3 /app/db.sqlite3
  python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','safepro_backend.settings'); import django; django.setup(); from django.utils import timezone; from products.models import SearchQuery; SearchQuery.objects.update(last_scraped_at=timezone.now(), status='ready', error=''); print('Seeded %d cached searches' % SearchQuery.objects.count())"
fi

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
