# Deployment

This document describes the supported, realistic deployment path for a
final-year project: **Docker Compose on a single VPS** (or any Docker-capable
host), with the mobile app built separately as a native binary via EAS Build.
It is deliberately simple — one process + PostgreSQL — while keeping every
production hardening toggle available.

A quick note up front: **the mobile app is not containerised.** A React Native /
Expo app ships as an APK/IPA; it only needs to *reach* the API over the network.
So "deploying ReuseHub" means (1) standing up the backend API, and (2) building
the app pointed at that API.

---

## Architecture of the deployment

```
                 ┌───────────────────────────────────────────────┐
  Android/iOS    │  VPS (Docker Compose)                          │
  (EAS build)    │                                               │
  ───────────▶   │  backend  ◀──▶  postgres:16   (pgdata volume) │
  HTTPS/IP       │    │  media/  (writable volume)                │
                 │    └── WhiteNoise serves static/ + media/      │
                 └───────────────────────────────────────────────┘
```

- `backend` — Django REST API served by **gunicorn** (2 workers default), with
  **WhiteNoise** serving `static/` and the API also serving uploaded `media/`.
- `db` — PostgreSQL 16, data on a named volume (`pgdata`).
- `media` — named volume so product images survive backend rebuilds.

## What has been made production-safe (Prompt 20)

- `DEBUG` defaults to `False` and **hard-fails** if `True` unless `ALLOW_DEV=True`
  (a guard against accidentally enabling debug in a live environment).
- `ALLOWED_HOSTS` comes from the environment (no wildcard in the shipped path).
- `SECURE_HTTP=True` enables: SSL redirect via `HTTP_X_FORWARDED_PROTO`,
  HSTS (1 year + preload), secure session/CSRF cookies, nosniff and
  `X-Frame-Options: DENY`. Docker Compose sets this by default.
- CORS: `CORS_ALLOW_ALL_ORIGINS` defaults to `False`; deployments must set an
  explicit `CORS_ALLOWED_ORIGINS` allow-list.
- Static files served by WhiteNoise with the manifest storage backend.
- Uploaded media served from the same Django process (single-host simplicity).

## Option A — Docker Compose (recommended)

Prerequisites: Docker + Docker Compose on the host.

### 1. Create a root `.env` (never committed)

Copy `backend/.env.example` to a root-level `.env` that Compose reads for
interpolation, and set real values. At minimum:

```bash
DJANGO_SECRET_KEY=<long random string>
POSTGRES_DB=reusehub
POSTGRES_USER=reusehub
POSTGRES_PASSWORD=<strong password>
ALLOWED_HOSTS=your.server.ip.or.domain
CORS_ALLOWED_ORIGINS=https://your-app.expo.dev
CLICKPESA_CLIENT_ID=
CLICKPESA_API_KEY=
CLICKPESA_WEBHOOK_SECRET=
SECURE_HTTP=True
```

> `DJANGO_SECRET_KEY` has **no default** — Compose will refuse to start if it is
> missing, which is the intended fail-fast behaviour.

### 2. Boot

```bash
docker compose up --build -d
docker compose logs -f backend     # watch migrations + gunicorn start
```

The API is now on `http://<host>:8000/`. Sanity check:

```bash
curl -s http://<host>:8000/api/products/ && echo             # public catalog
curl -s -o /dev/null -w "%{http_code}\n" http://<host>:8000/admin/  # 302 or 200
```

### 3. Create an admin user

```bash
docker compose exec backend python manage.py createsuperuser
```

### 4. Manage / inspect

```bash
docker compose ps
docker compose exec backend python manage.py showmigrations
docker compose down                  # stop
docker compose down -v               # stop and DELETE volumes (destroys data)
```

### 5. Putting it behind a domain + TLS

Compose exposes the API on port 8000 (HTTP). For a real demo you want TLS. The
simplest realistic option is a **Caddy reverse proxy** on the same host. Example
`Caddyfile`:

```
market.yourdomain.com {
    reverse_proxy 127.0.0.1:8000
}
```

Caddy obtains/autorenews Let's Encrypt certificates and sets
`X-Forwarded-Proto: https`, which the backend's `SECURE_HTTP` block reads to
enable SSL redirect + HSTS. Point `CORS_ALLOWED_ORIGINS` at the HTTPS origin and
rebuild.

## Option B — Bare VPS (no Docker)

Same as above but using the local virtualenv and gunicorn directly.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && $EDITOR .env        # DEBUG=False, fill secrets
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2
```

Use a systemd unit + Caddy/Nginx for persistence and TLS.

## Production security checklist (applied)

- [x] `DEBUG=False`; guarded against accidental `True`.
- [x] `ALLOWED_HOSTS` from env (no wildcard).
- [x] `CORS_ALLOW_ALL_ORIGINS=False`; explicit allow-list.
- [x] `SECURE_*` (HSTS, SSL redirect, secure cookies) gated behind `SECURE_HTTP`.
- [x] `DJANGO_SECRET_KEY` has no default.
- [x] Secrets only via env; nothing baked into the codebase or mobile bundle.
- [x] Static files via WhiteNoise; media served from the same host.

## No secrets in the mobile build

The mobile app uses **only** public, non-secret config via `EXPO_PUBLIC_*`
variables (`EXPO_PUBLIC_API_URL`). Real secrets (DB password, `DJANGO_SECRET_KEY`,
ClickPesa keys) exist only on the server. See the README build section and
`docs/BACKUP_STRATEGY.md` for the data-protection story.