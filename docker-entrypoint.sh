#!/bin/sh
# Entrypoint for the story2audio fleet image.
#
# Runs three jobs before handing off to uvicorn:
#   1. make the tenant's /data volume writable by the unprivileged runtime user
#   2. start the cache janitor, because nothing in the app ever expires audio_cache
#   3. drop root and exec the server
set -eu

PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"

# NOTE: this script must never chown/chmod /data. The provisioner creates the tenant's host
# directory (e.g. /var/lib/maplekiosk/tts), owns it, and manages its permissions. Touching it from
# inside the container rewrites the bind-mounted host directory's ownership and breaks the
# provisioner's next CreateVolume/redeploy with "chmod: Operation not permitted". The container runs
# as root (like MaplePOS), so it can write to /data regardless of what the provisioner sets.

# --- 1. cache janitor -----------------------------------------------------
# audio_cache has no TTL or size cap anywhere in main.py — every conversion is kept forever, so an
# unattended tenant fills its volume. Prune by mtime on an hourly loop. Set CACHE_MAX_AGE_DAYS=0 to
# disable and keep the upstream keep-everything behaviour.
CACHE_MAX_AGE_DAYS="${CACHE_MAX_AGE_DAYS:-30}"
if [ "$CACHE_MAX_AGE_DAYS" -gt 0 ] 2>/dev/null; then
    echo "[entrypoint] cache janitor on: pruning /data entries older than ${CACHE_MAX_AGE_DAYS}d, hourly"
    (
        while true; do
            # -mtime +N is "strictly older than N days", which is what we want; a file still being
            # written during a long conversion has a fresh mtime and is never a candidate.
            find /data -type f -mtime "+${CACHE_MAX_AGE_DAYS}" -delete 2>/dev/null || true
            sleep 3600
        done
    ) &
else
    echo "[entrypoint] cache janitor off (CACHE_MAX_AGE_DAYS=0); /data grows without bound"
fi

# --- 2. serve -------------------------------------------------------------
# Single worker, deliberately. main.py keeps in-flight job state in the module-level dicts
# generation_status / _generation_locks (main.py:89-90), so a second worker process would answer
# /tts/status and /tts/stream for jobs it knows nothing about. Scale by adding tenants, not workers.
#
# --proxy-headers + --forwarded-allow-ips: the provisioner fronts the container, so honour
# X-Forwarded-* and log real client IPs instead of the proxy's.
echo "[entrypoint] starting story2audio ${APP_VERSION:-dev} on ${HOST}:${PORT}"

exec /app/.venv/bin/uvicorn main:app \
    --host "$HOST" --port "$PORT" \
    --workers 1 \
    --proxy-headers --forwarded-allow-ips='*'
