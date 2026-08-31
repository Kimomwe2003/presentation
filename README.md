# ReuseHub

A marketplace app for buying, selling, and reusing second-hand goods — with
in-app chat, wallet payments, and an admin dashboard. Built as a final-year
engineering project across **20 prompts**, from architecture through production
readiness.

```
backend/   Django REST Framework API (Python 3.12, PostgreSQL)
mobile/    Expo / React Native app (TypeScript)
docs/      Architecture, security, deployment, and backup docs
```

---

## Table of contents

1. [Project overview](#project-overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Backend setup](#backend-setup)
5. [Mobile setup](#mobile-setup)
6. [Collaborator / Friend Setup Guide](#collaborator--friend-setup-guide)
7. [Environment variables](#environment-variables)
8. [Running tests](#running-tests)
9. [Building a distributable app](#building-a-distributable-app)
10. [Deployment](#deployment)
11. [Demo walkthrough](#demo-walkthrough)

---

## Project overview

ReuseHub lets people list second-hand goods for sale, browse and buy them, chat
with other users, pay through a mobile-money gateway (ClickPesa), and let sellers
withdraw their earnings. Administrators get a dashboard (sales stats, product
moderation, user management, withdrawals queue) and a full audit log of every
meaningful action.

Key features:

- JWT authentication with token rotation + blacklisting
- Product catalog with search, filters, favorites, and image uploads
- Cart → checkout → order lifecycle with a strict state machine
- ClickPesa USSD-push payments with checksum-verified webhooks
- Seller wallet + ledger (source of truth), 6% platform fee, withdrawals
- 1:1 chat (product-scoped & direct), in-app notifications
- Buyer/seller reviews and ratings
- Admin dashboard + complete audit log
- Production hardening: secure settings, throttling, password validators,
  financial-consistency & concurrency tests (see `docs/SECURITY_AUDIT.md`)

See `docs/PROJECT_STATUS.md` for the full prompt-by-prompt build log and honest
scope notes.

## Architecture

The system is a **Django REST API** (PostgreSQL) consumed by an **Expo/React
Native** app. A complete breakdown — data model, every Prompt 01–20 stage, API
layout, and design decisions — lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — architecture, apps, endpoints, prompt history
- [`docs/CLICKPESA_INTEGRATION.md`](docs/CLICKPESA_INTEGRATION.md) — payment flow & webhook verification
- [`docs/SECURITY_AUDIT.md`](docs/SECURITY_AUDIT.md) — security checklist & audit findings
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — production deployment guide
- [`docs/BACKUP_STRATEGY.md`](docs/BACKUP_STRATEGY.md) — database/media backup plan

## Prerequisites

- **Python 3.12+**
- **PostgreSQL 14+** (running locally, or use the Docker path in [Deployment](#deployment))
- **Node.js 20+** and npm
- **ngrok** — required to expose your local Django server to the internet so that ClickPesa can deliver payment webhooks to your machine
- Optional: the **Expo Go** app on a phone (for instant device testing), or an
  EAS account for native builds

Check you have them:

```bash
python --version && node --version && psql --version && ngrok version
```

## Backend setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # then fill in real values (see below)
python manage.py migrate
python manage.py createsuperuser                    # admin/dashboard login
python manage.py runserver                          # API on http://localhost:8000
```

> `DEBUG=True` in the local `.env` also requires `ALLOW_DEV=True` (already in
> `.env.example`) — this is a deliberate guard so `DEBUG` can never silently leak
> into a deployment.

## Mobile setup

```bash
cd mobile
npm install
cp .env.example .env          # set EXPO_PUBLIC_API_URL (see below)
npm start                     # Expo dev server
```

Launch the app in **Expo Go** (scan the QR code) or press `a` / `i` for an
Android/iOS emulator.

> When testing on a real phone, `EXPO_PUBLIC_API_URL` must be set to your **public
> ngrok URL** (not `localhost`) so the phone can reach the backend from outside
> your machine. See the section below.


## Collaborator / Friend Setup Guide

This section is specifically for a **collaborator (friend)** who has cloned this project
and wants to run it on their own local machine — including full payment testing with
ClickPesa. Read this section **end to end** before starting.

> **Key insight:** ngrok is NOT shared. Each developer must run their **own ngrok tunnel**
> on their own machine and register **their own tunnel URL** in the ClickPesa Dashboard.
> The ClickPesa API credentials (Client ID, API Key, Webhook Secret) are shared — the
> project owner must send them to you privately (not via git).

---

### Part A — PostgreSQL Database Setup

Even if PostgreSQL is already installed on your machine, you must create the specific
database and user that this project expects. The default port `5432` is the same
everywhere, so you only need to create the DB objects.

#### 1. Open a PostgreSQL shell

```bash
sudo -u postgres psql
```

#### 2. Create the database user and database

```sql
-- Create a dedicated user (choose a strong password and put it in your .env)
CREATE USER reusehub WITH PASSWORD 'your_strong_password_here';

-- Create the database owned by that user
CREATE DATABASE reusehub OWNER reusehub;

-- Grant all privileges
GRANT ALL PRIVILEGES ON DATABASE reusehub TO reusehub;

-- Exit
\q
```

> **Note:** The database name `reusehub` and user `reusehub` match what
> `backend/.env.example` expects. If you use different names, update the
> `POSTGRES_*` variables in `backend/.env` accordingly.

#### 3. Verify the connection

```bash
psql -U reusehub -d reusehub -h localhost
# Should open a psql prompt without errors — then \q to exit
```

#### 4. Set PostgreSQL variables in `backend/.env`

```env
POSTGRES_DB=reusehub
POSTGRES_USER=reusehub
POSTGRES_PASSWORD=your_strong_password_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

---

### Part B — ClickPesa Credentials (shared by project owner)

ClickPesa credentials are **not stored in the git repository** (they are in `.env`,
which is in `.gitignore`). The project owner must send you the following values
**securely** (e.g., via encrypted message / WhatsApp — never plain email or chat):

| Variable | Where to get it |
|----------|-----------------|
| `CLICKPESA_CLIENT_ID` | ClickPesa Dashboard → Developers → App credentials |
| `CLICKPESA_API_KEY` | ClickPesa Dashboard → Developers → App credentials |
| `CLICKPESA_WEBHOOK_SECRET` | ClickPesa Dashboard → Developers → Checksum key (`CHK...`) |

Add them to your `backend/.env`:

```env
CLICKPESA_BASE_URL=https://api.clickpesa.com/third-parties
CLICKPESA_CLIENT_ID=<value from project owner>
CLICKPESA_API_KEY=<value from project owner>
CLICKPESA_WEBHOOK_SECRET=<value from project owner>
CLICKPESA_CURRENCY=TZS
```

> ⚠️ `CLICKPESA_WEBHOOK_SECRET` is the **same value** as `CLICKPESA_CHECKSUM_SECRET`.
> It is the `CHK...` key used to verify that incoming webhook calls are genuinely from
> ClickPesa (HMAC-SHA256 signature). Both variables must have the same value.

---

### Part C — ngrok Setup (your own tunnel, your own URL)

Because the original developer's ngrok URL pointed to **their machine**, you need to
set up your own ngrok tunnel. ClickPesa's webhook will then be routed to **your** machine.

#### 1. Install ngrok

```bash
# Option A — Official installer (recommended)
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Option B — Download directly from https://ngrok.com/download
# (unzip and move the binary to /usr/local/bin/ngrok)

# Verify installation
ngrok version
```

#### 2. Create a free ngrok account and authenticate

1. Go to [https://ngrok.com](https://ngrok.com) and sign up for a free account.
2. Copy your **Authtoken** from the ngrok dashboard.
3. Run:

```bash
ngrok config add-authtoken <your-authtoken-here>
```

You only need to do this once per machine.

#### 3. Start Django on all interfaces

> ⚠️ Always run Django with `0.0.0.0:8000` — NOT just `runserver`. The default
> `127.0.0.1` only listens locally and ngrok cannot tunnel into it.

```bash
cd backend
source myvenv/bin/activate          # or .venv/bin/activate if you used that name
python manage.py runserver 0.0.0.0:8000
```

#### 4. Start ngrok in a **separate terminal**

```bash
ngrok http 8000
```

ngrok will print output like:

```
Forwarding  https://abcd-1234-efgh.ngrok-free.app  ->  http://127.0.0.1:8000
```

Copy the `https://abcd-1234-efgh.ngrok-free.app` URL — you will need it in the next steps.

---

### Part D — Wire Everything Together

You now have your ngrok URL. Update **all four places** that need it:

#### 1. Update `backend/.env`

Open `backend/.env` and set (replace with your actual ngrok URL):

```env
NGROK_PUBLIC_URL=https://abcd-1234-efgh.ngrok-free.app
CLICKPESA_WEBHOOK_BASE_URL=https://abcd-1234-efgh.ngrok-free.app
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,abcd-1234-efgh.ngrok-free.app,.ngrok-free.app,*
```

Restart Django so it picks up the new values:

```bash
# Stop the running server (Ctrl+C), then:
python manage.py runserver 0.0.0.0:8000
```

#### 2. Update the ClickPesa Dashboard webhook URL

1. Log in to the **ClickPesa Merchant Dashboard** with the project owner's account
   (or ask the owner to do this step).
2. Go to **Developers → Webhook → Callback URL**.
3. Set it to:

```
https://abcd-1234-efgh.ngrok-free.app/api/payments/webhook/clickpesa/
```

4. Save. ClickPesa will now send payment confirmations to **your** machine.

> 💡 Only one webhook URL can be active at a time in the ClickPesa dashboard.
> When collaborating, whoever is actively testing payments should have their URL
> registered there.

#### 3. Update `mobile/.env`

Create (or edit) `mobile/.env`:

```env
EXPO_PUBLIC_API_URL=https://abcd-1234-efgh.ngrok-free.app/api
```

Restart the Expo dev server:

```bash
cd mobile
npx expo start
```

Scan the QR code with **Expo Go** on your phone.

---

### Part E — Run Migrations & Create Test Users

After the database is set up and `.env` is configured:

```bash
cd backend
source myvenv/bin/activate
python manage.py migrate              # creates all tables
python manage.py createsuperuser      # creates your admin account
```

Optionally create the standard test users used in the demo walkthrough:

```bash
python manage.py shell <<'PY'
from django.contrib.auth import get_user_model
User = get_user_model()
def upsert(email, pwd, staff=False, superuser=False):
    u, c = User.objects.get_or_create(username=email,
        defaults={'email': email, 'is_staff': staff, 'is_superuser': superuser})
    u.set_password(pwd); u.save()
    print(f"{'Created' if c else 'Updated'}: {email}")
upsert('admin@gmail.com',        '1234',     staff=True, superuser=True)
upsert('lidyakimomwe@gmail.com', '1234567',  staff=True)
upsert('sadakimomwe@gmail.com',  '12345678')
PY
```

---

### ⚠️ Every time you restart ngrok — update these 4 places

The **free tier of ngrok gives you a NEW URL every time you restart it.** This means
you must update everything below each time:

| # | File / Location | What to update |
|---|-----------------|----------------|
| 1 | `backend/.env` | `NGROK_PUBLIC_URL` |
| 2 | `backend/.env` | `CLICKPESA_WEBHOOK_BASE_URL` |
| 3 | `backend/.env` | `ALLOWED_HOSTS` (add the new subdomain) |
| 4 | `mobile/.env` | `EXPO_PUBLIC_API_URL` |
| 5 | ClickPesa Dashboard → Developers → Webhook | Callback URL |

Then restart Django (Ctrl+C → `python manage.py runserver 0.0.0.0:8000`) and Expo (`npx expo start`).

> 💡 **Pro tip:** To avoid this chore, upgrade to an ngrok paid plan which gives you
> a **fixed static domain** (e.g., `your-name.ngrok.app`). You configure it once and
> it never changes between restarts.

---

### Complete Collaborator Checklist

Use this checklist to confirm everything is in order before testing payments:

- [ ] PostgreSQL installed and running (`sudo systemctl status postgresql`)
- [ ] `reusehub` database and user created (`psql -U reusehub -d reusehub -h localhost`)
- [ ] `backend/.env` exists (copied from `.env.example`) with all values filled in
- [ ] `POSTGRES_*` variables in `backend/.env` match your local DB credentials
- [ ] ClickPesa credentials (`CLIENT_ID`, `API_KEY`, `WEBHOOK_SECRET`) received from project owner and added to `backend/.env`
- [ ] ngrok installed and authenticated (`ngrok version` works)
- [ ] Django running on `0.0.0.0:8000` (not `127.0.0.1`)
- [ ] ngrok tunnel running and URL copied
- [ ] `backend/.env` updated with ngrok URL (`NGROK_PUBLIC_URL`, `CLICKPESA_WEBHOOK_BASE_URL`, `ALLOWED_HOSTS`)
- [ ] Django restarted after `.env` changes
- [ ] ClickPesa Dashboard webhook URL updated to your ngrok URL
- [ ] `mobile/.env` updated with `EXPO_PUBLIC_API_URL` pointing to your ngrok URL
- [ ] Expo dev server restarted
- [ ] `python manage.py migrate` run successfully
- [ ] Test users created or `createsuperuser` done

---

## Run on a New Machine (Quick Reference)

If you are already familiar with the setup, here is the quick reference:

### Step 1 — Start Django on **all interfaces**

> ⚠️ Never use plain `runserver` — it binds to `127.0.0.1` only and ngrok cannot reach it.

```bash
cd backend
source myvenv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

### Step 2 — Start ngrok and copy the public URL

```bash
ngrok http 8000
# → Forwarding  https://xxxx-xxxx.ngrok-free.app  →  http://127.0.0.1:8000
```

Copy the `https://xxxx-xxxx.ngrok-free.app` URL.

### Step 3 — Update `backend/.env`

Open `backend/.env` and set these three lines (replace the URL with yours):

```env
NGROK_PUBLIC_URL=https://xxxx-xxxx.ngrok-free.app
CLICKPESA_WEBHOOK_BASE_URL=https://xxxx-xxxx.ngrok-free.app
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,xxxx-xxxx.ngrok-free.app,.ngrok-free.app,*
```

Restart Django after saving:

```bash
pkill -f "manage.py runserver"
python manage.py runserver 0.0.0.0:8000
```

### Step 4 — Update the **ClickPesa Dashboard** webhook URL

Go to **ClickPesa Dashboard → Developers → Webhook → Callback URL** and set:

```
https://xxxx-xxxx.ngrok-free.app/api/payments/webhook/clickpesa/
```

### Step 5 — Update `mobile/.env`

Create `mobile/.env`:

```env
EXPO_PUBLIC_API_URL=https://xxxx-xxxx.ngrok-free.app/api
```

Then restart Expo:

```bash
cd mobile
npx expo start
```

Scan the QR code with **Expo Go** on your phone.

## Environment variables

### Backend — `backend/.env` (copy from `.env.example`, never commit)

| Variable | Required | Notes |
|----------|----------|-------|
| `DJANGO_SECRET_KEY` | yes | Random 50-char string; **no default** |
| `DEBUG` | yes | `False` for any deployment; `True` locally with `ALLOW_DEV=True` |
| `ALLOWED_HOSTS` | yes | e.g. `localhost,127.0.0.1`; no wildcard in production |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_HOST` / `POSTGRES_PORT` | yes | PostgreSQL connection |
| `CORS_ALLOWED_ORIGINS` | no | Comma-separated allowed origins |
| `CORS_ALLOW_ALL_ORIGINS` | no | Default `False`; keep `False` in production |
| `JWT_ACCESS_TOKEN_LIFETIME_DAYS` / `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | no | Default 1 / 7 |
| `CLICKPESA_BASE_URL` / `CLICKPESA_CLIENT_ID` / `CLICKPESA_API_KEY` / `CLICKPESA_WEBHOOK_SECRET` / `CLICKPESA_CURRENCY` | no | Payment gateway (see docs/CLICKPESA_INTEGRATION.md) |
| `SECURE_HTTP` | no | Default `False`; `True` behind TLS enables HSTS/SSL-redirect/secure cookies |
| `ALLOW_DEV` | no | Default `False`; required to run with `DEBUG=True` locally |
| `THROTTLE_*` | no | Optional override of global/scoped rate limits |
| `TIME_ZONE` | no | Default `UTC` |

### Mobile — `mobile/.env` (copy from `.env.example`)

| Variable | Required | Notes |
|----------|----------|-------|
| `EXPO_PUBLIC_API_URL` | yes | API base URL, e.g. `http://192.168.1.10:8000/api` or your deployed URL |

> Only `EXPO_PUBLIC_*` variables are inlined into the app bundle. **Never** put
> real secrets (DB passwords, `DJANGO_SECRET_KEY`, ClickPesa keys) in the mobile
> project — they live only on the server.

---

## Running tests

### Backend (pytest) — requires a running PostgreSQL

```bash
cd backend
source .venv/bin/activate
python manage.py check                      # quick sanity
pytest -q                                   # full suite (Prompt 19 regression)
ruff check .                                # lint
python manage.py makemigrations --check     # no missing migrations
```

The full suite covers the unit/API/state-machine/concurrency coverage built up
across all 20 prompts (including the Prompt 19 financial-consistency and security
tests). It takes a few minutes.

### Mobile (Jest + TS + ESLint)

```bash
cd mobile
npm test                 # unit tests
npm run typecheck        # tsc --noEmit
npm run lint             # expo lint
npm run format:check     # prettier
```

---

## Building a distributable app

Configuration lives in `mobile/eas.json` and `mobile/app.json`. The mobile app
reads the API base URL from `EXPO_PUBLIC_API_URL` **at build time**, so set it
before building.

### Option 1 — Expo Go (fastest for a demo)

No build needed. Run `npm start` and open the project in Expo Go on your device
(dev build profile or the default dev server). Use your machine's LAN IP in
`EXPO_PUBLIC_API_URL` when the phone is on the same network.

### Option 2 — EAS Build APK (installable Android demo)

```bash
cd mobile
npm install -g eas-cli
cp .env.example .env
# set EXPO_PUBLIC_API_URL to your deployed backend, e.g.
#   EXPO_PUBLIC_API_URL=https://api.example.com/api
eas login                 # once
eas build:configure
eas build --platform android --profile preview --message "Demo APK"
```

`--profile preview` produces a direct-install **APK** (specified in `eas.json`).
When it finishes, download the `.apk` and install it on any Android device.

### Option 3 — EAS production build (Play Store / internal track)

```bash
eas build --platform android --profile production
```

This runs as a signed **app bundle** with `autoIncrement` versioning. Adding an
iOS build requires an Apple developer account:

```bash
eas build --platform ios --profile production
```

> Building iOS without a paid Apple account is not possible with EAS; for a
> demo on iPhone, use Option 1 (Expo Go). This is documented as a known
> limitation in `docs/PROJECT_STATUS.md`.

## Deployment

See **[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)** for the full guide. In short:

- **Docker Compose** (recommended): `backend/Dockerfile` + `docker-compose.yml`
  run gunicorn + PostgreSQL with hardened settings, static/media via WhiteNoise.
- **Bare VPS**: local venv + `gunicorn config.wsgi:application`.
- Production security (HSTS, SSL redirect, secure cookies, `DEBUG=False`, no
  wildcard hosts/CORS) is enabled by env flags and documented there.

## Demo walkthrough

A step-by-step script to demonstrate the **full buyer and seller journeys** live.
Assumes the backend is running (Docker or `runserver`) and the mobile app is open
concurrently (a second backend account can be used via Expo Go / an emulator, or
by registering two users).

### 0. Prepare

1. Start the backend (see [Backend setup](#backend-setup)).
2. Open the app. Register **two accounts**: `buyer@example.com` and
   `seller@example.com` (Password: `StrongPass123!`).

### 1. Seller lists a product

1. Log in as `seller@example.com`.
2. Tap the **(+)** / **Sell** tab → **Create listing**.
3. Add a name ("Used laptop"), description, price, condition, and upload a photo.
4. Publish. The product now appears in the catalog.

### 2. Buyer browses, searches & favorites

1. Log in as `buyer@example.com`.
2. On the **Home** tab, confirm the seller's product appears.
3. Use **Search** (keyword/keyword filter and category filter) — the listing shows up.
4. Tap the heart on the product card to **favorite** it; open it from Favorites.

### 3. Buyer adds to cart & checks out

1. Open the product → **Add to Cart**.
2. Go to the **Cart**, review the line item and totals.
3. **Checkout** → create the order. The order goes to `pending_payment`.

### 4. Chat

1. From the product page (as buyer), tap **Chat** to open a conversation with the
   seller; send a message.
2. Log in as seller (or use a second device) and read/reply in the **Chats** tab.

### 5. Payment (ClickPesa)

1. From the order screen, tap **Pay** and enter a Tanzanian phone number
   (`255712345678`).
2. In production, ClickPesa returns a checksum-verified webhook that marks the
   order **paid** (see `docs/CLICKPESA_INTEGRATION.md` for the flow and the
   credentials required). ClickPesa is a live gateway, so a live USSD push needs
   a configured ClickPesa application.
3. **Offline demo** (no live gateway): mark the order paid from the backend with
   `python manage.py shell` → call the mark-paid transition, or use the Django
   admin/order action, so the payment→fulfilment→wallet loop can be shown without
   real money.
4. Confirm the order reached `paid` and the **wallet** shows the seller's
   pending earnings.

### 6. Fulfillment & earnings

1. As seller, in **Orders / Selling**, run: **confirm → ship → deliver**.
2. As buyer, **complete** the order.
3. As seller, open **Wallet**: the 94% net earnings (after the 6% platform fee)
   are credited; request a **withdrawal**.

### 7. Admin dashboard & audit log

1. Open `http://localhost:8000/admin/` and log in with the superuser created in
   [Backend setup](#backend-setup).
2. Inspect the status dashboard (sales, users, products).
3. Use the **Withdrawals** queue to approve the seller's payout.
4. Open the **Audit log** to show the recorded actions from this session
   (login, listing created, order placed, payment, withdrawal).

That is the whole loop: **list → browse → chat → buy → pay → fulfil → get paid →
admin oversight**, all recorded in the audit log.

---

## Documentation index

| Doc | Purpose |
|-----|---------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Full architecture & 20-prompt history |
| [`docs/CLICKPESA_INTEGRATION.md`](docs/CLICKPESA_INTEGRATION.md) | Payment gateway integration |
| [`docs/SECURITY_AUDIT.md`](docs/SECURITY_AUDIT.md) | Security audit & hardening |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Deployment guide (Docker/VPS) |
| [`docs/BACKUP_STRATEGY.md`](docs/BACKUP_STRATEGY.md) | Database & media backups |
| [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) | Final status, scope & future work |
| [`CLICKPESA_PAYMENT_ARCHITECTURE.md`](CLICKPESA_PAYMENT_ARCHITECTURE.md) | Full payment architecture blueprint (copy-paste ready) |
# presentation
