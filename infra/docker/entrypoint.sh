#!/bin/sh
set -euo pipefail

ROLE="${APP_ROLE:-web}"

mkdir -p /app/staticfiles /app/media

# wait for Postgres
PGHOST="${POSTGRES_HOST:-db}"
PGPORT="${POSTGRES_PORT:-5432}"
PGUSER="${POSTGRES_USER:-app}"
PGDB="${POSTGRES_DB:-app}"

i=0
until pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDB" >/dev/null 2>&1; do
  i=$((i+1))
  [ "$i" -ge 120 ] && echo "Postgres not ready" >&2 && exit 1
  sleep 1
done

# wait for Redis (optional password)
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"

if [ -n "$REDIS_PASSWORD" ]; then
  i=0
  until redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" PING | grep -q PONG; do
    i=$((i+1))
    [ "$i" -ge 120 ] && echo "Redis not ready" >&2 && exit 1
    sleep 1
  done
else
  i=0
  until redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" PING | grep -q PONG; do
    i=$((i+1))
    [ "$i" -ge 120 ] && echo "Redis not ready" >&2 && exit 1
    sleep 1
  done
fi

if [ "$ROLE" = "web" ]; then
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
  exec gunicorn lightbikeshop.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --threads "${GUNICORN_THREADS:-2}" \
    --timeout 60 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
elif [ "$ROLE" = "worker" ]; then
  exec celery -A lightbikeshop worker -l INFO
elif [ "$ROLE" = "beat" ]; then
  exec celery -A lightbikeshop beat -l INFO
else
  echo "Unknown APP_ROLE: $ROLE" >&2
  exit 1
fi
