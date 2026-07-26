# Runtime image for story2audio, built and pushed to GHCR by .github/workflows/release_container.yml
# for the provisioning system to `docker pull` + `docker run` per tenant.
#
# Unlike MaplePOS (whose workflow publishes first and whose Dockerfile only packages the output), a
# Python app's "publish" step *is* the dependency install, so that happens here in a builder stage.
# The runtime stage stays lean: interpreter + the resolved virtualenv + source, no build tooling.

# ---------------------------------------------------------------------------
# Stage 1 — resolve dependencies into a self-contained virtualenv at /app/.venv
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

WORKDIR /app

# Dependency manifests only, so this layer caches across source-only changes.
COPY pyproject.toml uv.lock README.md ./

# --frozen installs the lockfile verbatim (no re-resolution), so an image built today and one built
# in six months contain byte-identical dependencies. If this ever fails the lock is stale — run
# `uv lock` locally and commit the result rather than relaxing this flag.
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Stage 2 — runtime
# ---------------------------------------------------------------------------
FROM python:3.13-slim

# tini reaps zombies and forwards SIGTERM so `docker stop` doesn't sit through the 10s timeout.
#
# Deliberately NO unprivileged user and no gosu: the container runs as root, exactly like MaplePOS.
# The provisioner creates and owns the tenant's host directory (e.g. /var/lib/maplekiosk/tts) and
# manages its permissions itself. An earlier revision chowned /data on startup to support running
# unprivileged, which rewrote the ownership of the bind-mounted host directory out from under the
# provisioner and broke its redeploy with "chmod: Operation not permitted". Leave /data alone.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# story2audio writes every artifact it must keep (mp3 / json / srt / vtt / cues) to
# <source dir>/audio_cache — a hard-coded path derived from main.py's own location (main.py:53).
# The provisioner mounts each tenant's persistent volume at /data, so symlink that path onto the
# volume: all cache writes follow the link and survive container recreation on redeploy.
# No app change needed — main.py's os.makedirs(CACHE_DIR, exist_ok=True) is happy with a symlink
# that resolves to an existing directory.
RUN mkdir -p /data && ln -s /data /app/audio_cache

# Source last: it changes on every commit, so it must not invalidate the dependency layers.
COPY --from=build /app/.venv /app/.venv
COPY . /app

# The entrypoint is the only file that needs the executable bit.
RUN chmod +x /app/docker-entrypoint.sh

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}" \
    HOST=0.0.0.0 \
    PORT=8080

# Baked at build time by the release workflow (--build-arg APP_VERSION=...); main.py:48 surfaces it
# on /health, which is how you confirm which tag a running tenant is actually on.
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

# Listen on 8080 inside the container — the fleet-wide container port the provisioner maps a
# per-tenant host port to (same as MaplePOS). Keep in sync with the catalog row's InternalPort.
EXPOSE 8080

# Cheap liveness signal for the provisioner. Uses the interpreter that is already in the image
# rather than pulling in curl. /health is a plain JSON handler with no TTS work behind it.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/health', timeout=4).status==200 else 1)"]

ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker-entrypoint.sh"]
