# ReuseHub — Final Project Status

Status of ReuseHub after all **20 prompts** of the master architecture series. This
document is the single source of truth for what was built, what is verified, the
known limitations, and honest notes on future work — written from the final state
of the codebase, not the original plan.

---

## What was built

A full-stack marketplace for second-hand goods:

- **Backend**: Django 6.1 REST Framework API on PostgreSQL (13 apps), served by
  gunicorn with WhiteNoise and hardened settings.
- **Mobile**: Expo / React Native (SDK 57, RN 0.86, TypeScript) app with full
  navigation, secure token storage, and an Axios client with refresh-on-401.
- **Docs**: architecture, ClickPesa integration, security audit, deployment, and
  backup strategy.

### Feature coverage, prompt by prompt

| # | Prompt | Delivered |
|---|--------|-----------|
| 01 | Architecture & setup | Monorepo, Django project, PostgreSQL wiring, DRF, env-driven settings |
| 02 | Accounts | Custom user + profile, JWT register/login/refresh/logout, `/api/users/me/` |
| 03 | Catalog models | Category/Product/ProductImage/Favorite models + DB constraints |
| 04 | Catalog API | Product CRUD/scoped listing, search, filters, favorites |
| 05 | Mobile skeleton | Auth gate + bottom tabs, token storage, refresh-on-401 client, Login/Register |
| 06 | Marketplace UI | Browse/search/filter/favorites; product browsing/selling screens planned |
| 07 | Cart + orders | Cart (anon+user) & order creation backend |
| 08 | Order lifecycle | Multi-seller state machine, per-item fulfilment, buyer/seller order screens |
| 09 | Payments | ClickPesa USSD-push, checksum-verified webhooks, manual verify |
| 10 | Wallet/ledger | Ledger-as-source-of-truth, 6% platform fee, Decimal discipline |
| 11 | Mobile marketplace | Category browse, search/filter UI, product detail + chat within catalogue |
| 12 | Withdrawals | Withdrawal requests, hard-debit reservation, admin transitions, atomic reversal |
| 13 | Chat | 1:1 product-scoped & direct conversations/messages |
| 14 | Notifications | In-app notification list + unread badge |
| 15 | Reviews | Product/seller reviews restricted to completed purchases |
| 16 | Admin panel | Staff dashboard, user/product moderation, categories |
| 17 | Audit log | Append-only audit trail + staff reporting (fees/volume/new users) |
| 18 | Full-stack polish | Mobile cart + checkout, withdrawal UI, design system, journey E2E tests |
| 19 | Security & consistency | Password validators, throttling, JWT/suspension tests, financial-concurrency stress tests |
| 20 | Production readiness | Docker deploy, EAS builds, backup plan, final verification (this pass) |

## Verified behaviour (final checks)

These were re-verified live during Prompt 20 against a **fresh database**:

- [x] All 13 Django apps present; all 31 tables migrate cleanly from zero.
- [x] Full **buyer journey** (register → browse → cart → checkout → pay → track →
      fulfil → review) passes via the automated journey test.
- [x] Full **seller journey** (register → list → receive → fulfil → get paid →
      withdraw) passes via the automated journey test.
- [x] Admin dashboard (`/api/admin/dashboard/`) returns sales/users/products stats.
- [x] Audit log (`/api/audit-logs/`) is staff-readable and records actions.
- [x] Backend services accept connections with the documented env configuration.

## Test inventory (final)

### Backend — `backend/` (pytest, requires PostgreSQL)

| Suites | Covers |
|--------|--------|
| `accounts/tests.py` | register/login/JWT (incl. expiry, suspension, throttling) |
| `catalog/test_api.py`, `catalog/tests.py` | product/category CRUD, permissions, models |
| `cart/test_api.py`, `orders/test_api.py` + `test_state_machine.py` | cart, orders, every transition |
| `payments/test_payments.py`, `test_journeys.py`, `test_financial_consistency.py` | webhooks, buyer+seller journeys, ledger-reconciliation & concurrency |
| `wallet/tests.py`, `withdrawals/tests.py` | ledger, fee math, concurrency, withdrawal flows |
| `chat/tests.py`, `reviews/tests.py`, `notifications/tests.py` | messaging, reviews, notifications |
| `adminpanel/tests.py`, `auditlog/tests.py`, `core/tests.py` | admin API, audit log, core |

Plus a `test_no_float_used_for_money` AST rule enforcing Decimal-only money.

### Mobile — `mobile/` (Jest)

`__tests__/`: admin, auditlog, cart, client interceptors, config sanity,
notifications, reviews (API-wrapper + client unit tests).

## Known limitations & honest scope

This is a **final-year project**, not a production marketplace. The following are
deliberate, documented boundaries (per the "final-year project, not Alibaba"
principle):

### Deferred / not implemented
- **Real-time chat** — chat uses **polling**/on-demand message fetch, not
  WebSockets/Channels. Fine for a demo; live typing indicators are absent.
- **Push notifications** — in-app notifications exist; OS push (FCM/APNs) is not
  wired.
- **iOS native build** — EAS iOS build requires a paid Apple Developer account
  (documented in README). iPhone demo uses **Expo Go**.
- **Payment sandbox** — ClickPesa is a live gateway; a real USSD payment needs a
  configured ClickPesa application. Offline demo path (mark-paid via shell/admin)
  is documented in the README.
- **Media storage** — uploaded images are served from the same Django process
  (single-host). Object storage (S3) is out of scope but noted in DEPLOYMENT.

### Operational notes
- Backend tests need a reachable PostgreSQL (the Docker Compose path provides one).
- `ALLOWED_HOSTS`/CORS must be set per deployment; defaults are dev-only.
- Backups are manual/scheduled local dumps (see `docs/BACKUP_STRATEGY.md`), not an
  enterprise PITR solution.

## Suggested future enhancements

1. **WebSockets (Django Channels)** for real-time chat + presence.
2. **FCM/APNs push** for notifications users genuinely care about.
3. **Object storage (S3/MinIO)** + CDN for images at scale.
4. **Point-in-time backup (WAL archiving)** if real data tenure grows.
5. **Rate-limit + captcha on register/login** beyond the current throttling.
6. **Front-end E2E (Detox/Playwright)** on top of the current Jest unit coverage.
7. **Docker Compose MySQL→Postgres migration hash / golden DB tests** for schema regressions
   (low priority; migrations already gate this).

## How to verify this status yourself

Follow [`../README.md`](../README.md): backend + mobile setup, run the test
commands, then the **Demo walkthrough**. Deployment steps are in
[`DEPLOYMENT.md`](DEPLOYMENT.md); recovery steps in [`BACKUP_STRATEGY.md`](BACKUP_STRATEGY.md).

---

*Final status generated at the close of Prompt 20.*