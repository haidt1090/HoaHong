#!/bin/sh
set -eu

# Bind mounts / named volumes keep host or old-image ownership (often root).
# Prod image starts as root, fixes writable dirs, then drops to appuser.
# Dev image has no appuser — skip and keep running as the image user.
if [ "$(id -u)" = "0" ] && id appuser >/dev/null 2>&1; then
    mkdir -p /app/src/staticfiles /app/src/media /app/src/logs
    chown -R appuser:appuser /app/src/staticfiles /app/src/media /app/src/logs
    exec gosu appuser "$0" "$@"
fi

python <<'PY'
import os
import time

import psycopg

url = os.environ["DATABASE_URL"]
for attempt in range(1, 31):
    try:
        with psycopg.connect(url, connect_timeout=3) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        break
    except psycopg.OperationalError:
        if attempt == 30:
            raise
        time.sleep(2)
PY

python src/manage.py migrate --noinput

# Worker/beat do not serve static files and do not mount static_files.
if [ "${1:-}" = "gunicorn" ]; then
    python src/manage.py collectstatic --noinput
fi

exec "$@"
