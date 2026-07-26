# story2audio — fleet deployment

Container host notes for the provisioning system. Same shape as MaplePOS: a GHCR image the
provisioner pulls and runs per tenant, with the tenant's persistent volume mounted at `/data`.

## Catalog row

| Field             | Value                             |
| ----------------- | --------------------------------- |
| `ImageRepository` | `ghcr.io/ericngo1972/story2audio` |
| `ImageTag`        | the released version, e.g. `3.1.0` |
| `InternalPort`    | `8080`                            |
| Volume mount      | `/data`                           |
| Health endpoint   | `GET /health` → `{"ok":true,"version":"..."}` |
| Replicas          | **1 per tenant** (see below)      |

Pin the row to a version tag. `:latest` only moves when someone runs the Release Container
workflow, and `:edge` / `:<sha>` move on every push to `main` — neither is a deployment target.

## Publishing an image

GitHub → Actions → **Release Container** → Run workflow → enter the version (e.g. `3.1.0`).

It builds `linux/amd64`, pushes `:<version>` and `:latest`, bakes the version in as `APP_VERSION`,
and prints the catalog row in the run summary. `APP_VERSION` is what `/health` reports, so you can
always confirm which tag a running tenant is actually on.

## Runtime contract

**Port.** The app listens on `$PORT` (default `8080`). Change it by setting `PORT`; `EXPOSE` and the
image healthcheck both follow it.

**State.** Everything story2audio must keep — generated `.mp3`, plus the `.json` / `.srt` / `.vtt` /
`.cues.json` / `.cues.jsonl` sidecars — goes to `audio_cache`, a path main.py derives from its own
location (`main.py:53`) and cannot be configured. The image symlinks `/app/audio_cache → /data`, so
mounting the tenant volume at `/data` captures all of it with no app change. Nothing else in the
container is worth persisting.

**Permissions.** The container starts as root only long enough to `chown /data`, then drops to the
unprivileged `story2audio` user (uid 10001) via `gosu`. That covers both an empty named volume
(root-owned on first mount) and a host bind mount.

**Secrets.** None required. `PROXY` (see `.env.example`) is the only sensitive variable, and only if
this tenant must reach the TTS providers through an authenticated proxy.

## Environment variables

| Variable             | Default  | Notes |
| -------------------- | -------- | ----- |
| `PORT`               | `8080`   | Must match the catalog's `InternalPort`. |
| `HOST`               | `0.0.0.0`| Leave as-is. |
| `CACHE_MAX_AGE_DAYS` | `30`     | Cache janitor; `0` disables it. See below. |
| `PROXY`              | unset    | `http://user:pass@host:port`. Applied to both edge-tts and outbound HTTP. |
| `ENABLE_DEBUG_TTS`   | unset    | Exposes `POST /tts/debug/chunks`. Leave off in production. |
| `APP_VERSION`        | baked in | Set by the release workflow; don't override. |
| `TZ`                 | —        | Only affects log timestamps. |

## Things that will bite you

**Run exactly one replica per tenant.** In-flight conversion state lives in module-level dicts —
`generation_status` and `_generation_locks` (`main.py:89-90`) — not on disk or in a shared store. A
second replica would answer `/tts/status/{id}` and the streaming endpoints for jobs it has never
heard of. Completed conversions *are* durable (they're on `/data`), so this only affects jobs in
flight; scale by adding tenants, not workers. The entrypoint pins `uvicorn --workers 1` to enforce
this inside the container.

**Disable proxy buffering.** Three endpoints stream — `/tts/cues/stream/{id}` and
`/tts/stream/{id}` are `text/event-stream` (main.py:1683, 1793) and the audio path is chunked
`audio/mpeg` (main.py:1870). Live playback and live subtitles are the product; a buffering reverse
proxy turns both into "nothing happens, then everything arrives at once."

- nginx: `proxy_buffering off; proxy_read_timeout 3600s;`
- Traefik: buffering is off by default — just don't attach a `buffering` middleware.
- Cloudflare tunnel: SSE passes through, but keep the origin request timeout generous.

Long conversions hold a connection open for minutes, so set idle/read timeouts well above the
default 60s.

**Outbound network is required.** edge-tts opens a websocket to Microsoft's speech endpoint and the
gTTS fallback calls `translate.google.com`. A tenant with no egress will accept text and then fail
every conversion. If egress is restricted, set `PROXY`.

**The cache never expires on its own.** Nothing in main.py deletes a completed conversion — the only
cleanup paths remove *incomplete* or runtime files (`main.py:267`, `main.py:285`). Left alone a busy
tenant fills its volume. The entrypoint therefore runs an hourly `find /data -mtime +N -delete`,
default 30 days, controlled by `CACHE_MAX_AGE_DAYS`. Set it to `0` for upstream keep-forever
behaviour, and size the volume accordingly.

**Cold cache after a volume change.** Cache IDs are content hashes, so a wiped or swapped volume
doesn't corrupt anything — every conversion is simply regenerated on next request.

## Local verification

```bash
docker compose up -d --build
curl -s localhost:8080/health          # {"ok":true,"version":"dev"}
docker compose logs -f app
```

Then open `http://localhost:8080`, paste text, and confirm audio starts playing before generation
finishes — that is the end-to-end check that streaming survived the proxy path.

To run a released image instead of building:

```bash
IMAGE_TAG=3.1.0 docker compose up -d --pull always --no-build
```
