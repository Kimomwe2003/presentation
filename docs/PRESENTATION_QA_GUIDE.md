# ReuseHub — Final Year Project Presentation Defense: Complete Question & Answer Guide

This document lists **every question you can expect** from internal examiners, supervisors, and external panel members during your final-year project defense — together with **complete, technically accurate answers** grounded in the actual ReuseHub codebase (`backend/`, `mobile/`, `docs/`).

> Accuracy notes: figures in this guide come from the current code, not the plan. Expo SDK is **54** (not 57), the backend test suite has **316 tests** (not 109), and the audit log has **25** standard action codes. Use the cheatsheet at the end during prep.

---

## Table of Contents
1. [Category 1: Project Overview, Problem Statement & Architecture](#category-1-project-overview-problem-statement--architecture)
2. [Category 2: Database Design, Constraints & Data Integrity](#category-2-database-design-constraints--data-integrity)
3. [Category 3: Authentication, Authorization & Security](#category-3-authentication-authorization--security)
4. [Category 4: Order Lifecycle & State Machine Architecture](#category-4-order-lifecycle--state-machine-architecture)
5. [Category 5: Financial Management, Ledger System & Platform Fee](#category-5-financial-management-ledger-system--platform-fee)
6. [Category 6: Payment Gateway Integration (ClickPesa & Webhooks)](#category-6-payment-gateway-integration-clickpesa--webhooks)
7. [Category 7: Real-Time Communication & Messaging Architecture](#category-7-real-time-communication--messaging-architecture)
8. [Category 8: Audit Logging, Admin Moderation & Reporting](#category-8-audit-logging-admin-moderation--reporting)
9. [Category 9: Mobile Client (React Native / Expo) & UX Architecture](#category-9-mobile-client-react-native--expo--ux-architecture)
10. [Category 10: Testing, Quality Assurance, Concurrency & Deployment](#category-10-testing-quality-assurance-concurrency--deployment)
11. [Category 11: Known Limitations, Scope & Challenge ("Gotcha") Questions](#category-11-known-limitations-scope--challenge-gotcha-questions)
12. [Quick Reference Metrics & Tech Specs Cheatsheet](#quick-reference-metrics--tech-specs-cheatsheet)

---

## Defense Strategy Tips (read first)

* **Be direct and concrete.** If asked "Why did you choose X over Y?" answer with: *"We chose X because [reason/requirement] — it satisfied our need for [performance/security/simplicity]. Y offered [benefit], but introduced [cost], such as [dependency/complexity]."*
* **Show domain understanding.** Emphasize how technical decisions solve real East-African marketplace problems: mobile-money reliability, race conditions in wallets, expensive/exhausted customers being charged twice, token security on devices.
* **Name industry standards you implemented:** JWT (RFC 7519), HMAC-SHA256 webhook signing, `Decimal` money math, DB transactions/ACID, double-entry ledger principles, `SELECT ... FOR UPDATE` pessimistic locking, append-only audit trails, throttling, canonical JSON checksums.
* **Be honest about scope.** This is a final-year project, not Alibaba. When asked about production gaps, say "We documented that as a deliberate boundary in `docs/PROJECT_STATUS.md`, and it is a listed future enhancement (WebSockets, push notifications, object storage)." Honesty scores higher than bluffing.

---

## Category 1: Project Overview, Problem Statement & Architecture

### Q1.1 What is ReuseHub, and what problem does it solve?
**Answer:**
ReuseHub is a peer-to-peer (P2P) second-hand marketplace app for buying, selling, and reusing pre-owned goods. It solves three concrete problems seen in typical local marketplace experiences: (1) **no integrated local payment channel** — so we integrated ClickPesa mobile-money (Tigo Pesa, M-Pesa, Airtel Money) USSD-push collection in Tanzanian Shillings (TZS); (2) **buyer–seller trust and negotiation** — so we built in-app product-scoped chat, reviews that are restricted to completed purchases, and a full order lifecycle with tracking; and (3) **platform accountability** — every meaningful action is written to an append-only audit log, and sellers are paid through a transparent ledger with a documented 6% platform fee.

### Q1.2 Who are the key stakeholders, and what can each do?
**Answer:**
1. **Buyers** — browse pre-owned items, search/filter, favorite products, negotiate via in-app chat, add to cart, checkout, pay with mobile money (ClickPesa USSD push), track order fulfillment (confirm → ship → deliver), confirm receipt, and review purchased items/sellers.
2. **Sellers** — create listings (name, description, price, condition `NEW/LIKE_NEW/GOOD/FAIR/USED`, location, photos), manage their product status, receive orders, run fulfillment (`confirm → ship → deliver`), monitor pending earnings, and request withdrawals to a mobile-money number.
3. **Administrators** — get a dashboard with sales/users/products statistics, moderate listings (soft-delete to `INACTIVE` with a mandatory reason), manage users (suspend/activate/delete), process the withdrawals queue, and inspect the append-only audit log and daily reports.

### Q1.3 Explain the high-level system architecture.
**Answer:**
ReuseHub is a decoupled client-server system:
* **Backend API** — Django 6.1 REST Framework (Python 3.12), 13 apps (`core, accounts, catalog, cart, orders, payments, wallet, withdrawals, chat, notifications, reviews, adminpanel, auditlog`), served by Gunicorn using WhiteNoise for static files, backed by PostgreSQL in production.
* **Mobile app** — Expo/React Native (SDK 54, RN 0.81.5) with TypeScript; React Navigation for flow, Axios for HTTP with a refresh-on-401 interceptor, `expo-secure-store` for token persistence.
* **Payment gateway** — ClickPesa API for mobile-money USSD-push collection and payouts, with HMAC-SHA256-signed webhooks and manual-verify/reconciliation fallbacks.
* **Deployment/infrastructure** — Docker Compose (Gunicorn + PostgreSQL) for production, `render.yaml` for hosting, and ngrok tunneling during local webhook development.

### Q1.4 Why separate the backend REST API from the mobile frontend instead of a monolithic web app?
**Answer:**
1. **Multi-client readiness** — the REST API is a single source of truth that can power the mobile app, a future web app, or third-party integrations without rewriting business logic (catalog, payments, ledger, state machine).
2. **Separation of concerns** — the mobile team handles UI/UX, client state, and offline behavior; the backend owns business rules, transactions, concurrency, and security.
3. **Independent scaling** — the stateless API can be scaled behind a load balancer while mobile assets live on devices.

### Q1.5 Why Django and Django REST Framework instead of Node.js, Express, or FastAPI?
**Answer:**
* Django's **batteries-included** ecosystem gave us the ORM, migrations, admin, authentication (SimpleJWT), throttling, validators, and testing tools out of the box, which is ideal for a feature-dense final-year scope.
* The **ORM + migration system** guarantees schema changes are versioned and reversible — critical because we built 13 apps across 20 incremental prompts.
* DRF's **GenericViewSets, routers, pagination, and permission classes** let us expose consistent REST endpoints very quickly while enforcing object-level permissions.
* Django's **transaction management (`transaction.atomic()`, `select_for_update()`)** is mature and reliable for the financial code (ledger, withdrawals).

### Q1.6 Why React Native with Expo instead of Flutter or native apps?
**Answer:**
* **Single TypeScript codebase** compiled to both iOS and Android — ideal for a final-year demo and for teammates working in the same language ecosystem.
* **Expo tooling** (Expo Go fast iteration, EAS Build for installable APKs, asset handling, camera/image-picker, secure-store, QR generation) removed most native build complexity so we could focus on the marketplace product logic.
* **`expo-secure-store`** gives hardware-backed token storage (iOS Keychain / Android Keystore) which plain AsyncStorage cannot.
* We documented the trade-off: native (Swift/Kotlin) gives more control but doubles the work — unjustifiable for this scope.

### Q1.7 How is the codebase organized?
**Answer:**
It is a monorepo with three folders:
* `backend/` — Django project with 13 apps, `requirements.txt`, `Dockerfile`, `.env.example`, and a `pyproject.toml`/`ruff` lint config.
* `mobile/` — Expo app with `App.tsx`, `src/` (api, context, hooks, navigation, screens, components, theme, utils), `app.json`, `eas.json`, Jest tests in `__tests__/`.
* `docs/` — `ARCHITECTURE.md`, `CLICKPESA_INTEGRATION.md`, `SECURITY_AUDIT.md`, `DEPLOYMENT.md`, `BACKUP_STRATEGY.md`, `PROJECT_STATUS.md`, and this guide.
Plus `docker-compose.yml`, `render.yaml`, and this README at the root.

### Q1.8 Walk me through the complete user journey end to end.
**Answer:**
The full loop, which is automated in `payments/test_journeys.py`, is:
1. **Seller lists a product** (`POST /products/`, then uploads images).
2. **Buyer registers/logs in** (JWT), **searches/filters**, **favorites**, **opens chat** with the seller.
3. **Buyer adds to cart** → **checks out** (`POST /orders/`) → order enters `pending_payment`.
4. **Buyer pays** via ClickPesa USSD push; a verified webhook calls `/api/clickpesa/webhook/` and the state machine moves the order to `paid`. The seller's **pending earnings** are projected and products are marked `SOLD`.
5. **Seller fulfills** (`confirm → ship → deliver`); **buyer confirms receipt** (`complete`); a **ledger credit** is posted (94% net after the 6% platform fee).
6. **Seller withdraws** earnings; **admin approves** the withdrawal; the **audit log** records every step.

---

## Category 2: Database Design, Constraints & Data Integrity

### Q2.1 What database system did you use and why?
**Answer:**
**PostgreSQL 14+** in production, with SQLite as a local-dev default (`USE_SQLITE` env flag). Reasons for Postgres:
1. **ACID + row-level locking** — `SELECT ... FOR UPDATE` and transaction isolation are essential for the financial ledger and withdrawal reservation logic.
2. **Enforced constraints** — DB `CheckConstraint`s and `UniqueConstraint`s guarantee integrity even if application checks were bypassed.
3. **Aggregations** — `TruncDate` and grouping power the admin daily reports (`/api/admin/reports/summary/`).
4. **JSON supports** (`JSONField` for shipping address and product attributes).
The migration creates **31 tables** cleanly from zero across the 13 apps.

### Q2.2 How do you enforce data integrity at the database level versus the application layer?
**Answer:**
We use defense in depth:
* **Database engine:**
  - `Product`: `CheckConstraint(price > 0)`, `CheckConstraint(quantity >= 0)`.
  - `Wallet`: `CheckConstraint(balance >= 0)` — no overdrafts even under race conditions.
  - `Cart`: `CheckConstraint(owner XOR session_key)` — exactly one identity, never both/neither.
  - `Favorite`: `UniqueConstraint(user, product)`.
  - `Review`: `UniqueConstraint(order_item)` and `CheckConstraint(rating BETWEEN 1 AND 5)`.
  - `LedgerTransaction`: `UniqueConstraint(order_item, type)` — DB-level idempotency for earnings.
  - `WithdrawalRequest`: `CheckConstraint(amount >= 500)`.
* **Application layer:** model `clean()` methods, DRF serializer validation (permissions, transitions, stock), image validators, and service-layer guard functions.

### Q2.3 How did you design the Cart to handle both anonymous and logged-in users?
**Answer:**
`Cart` has `owner` (OneToOne to User, nullable) and `session_key` (string, nullable), with a DB `CheckConstraint` enforcing exactly one is set. `cart/services.py`:
* `get_or_create_cart_for_user()` → owner cart with a 30-day expiry.
* `get_or_create_anonymous_cart()` → session-keyed cart.
* `get_current_cart()` drops items whose product is `SOLD`/`INACTIVE`.
* **Merge** (`merge_anonymous_cart_to_user`): on login/checkout the anonymous items are copied into the user cart inside `transaction.atomic()`, identical (product, attributes) rows are merged by quantity **up to a cap of 100**, and the anonymous cart is deleted.

### Q2.4 How does the schema support an order containing items from multiple sellers?
**Answer:**
With a **Two-Tier Order Model**:
* `Order` is the buyer's payment envelope: `order_number`, `buyer`, `status` (`pending_payment`, `paid`, `confirmed`, `shipped`, `delivered`, `completed`, `cancelled`, `payment_failed`, `refunded`), `subtotal`, `shipping_cost`, `total`.
* `OrderItem` is per-seller fulfillment: links to `seller` + `product`, snapshots `product_name`, `product_sku`, `unit_price`, `quantity`, and carries its own `item_status` (`pending`, `confirmed`, `shipped`, `delivered`, `completed`, `cancelled`).
Each seller manages only their own line items; when every item is `completed`, the parent `Order` auto-transitions to `completed`.

### Q2.5 How are product images validated and stored?
**Answer:**
`catalog/validators.py` runs four checks in order: **extension** (`.jpg/.jpeg/.png/.webp/.gif`), **MIME type** (`image/jpeg/png/webp/gif`), **size (max 5 MB)**, then the expensive one, **Pillow `Image.verify()`** content decoding. Images upload to `products/<product_id>/<uuid>.ext`; the model's `save()` calls `full_clean()` so rules run even on direct ORM saves. Deleting the primary image auto-promotes the next one.

### Q2.6 How is search and filtering implemented?
**Answer:**
On `ProductViewSet`: **django-filter** for `min_price`, `max_price`, `location`, `category`, `condition`, `status`, `seller`; **DRF SearchFilter** on `name` and `description`; **OrderingFilter** on `created_at`, `price`, `name`. Pagination is `CatalogPagination` — **page size 20, max 100** — and the mobile feed simply follows the DRF `next` link.

### Q2.7 Why use DecimalField for money instead of float?
**Answer:**
Float binary representation cannot exactly represent values like `0.06` or `0.1`, causing silent rounding drift in money. All monetary fields are `DecimalField`, `wallet/services.py` hard-rejects floats (`_as_decimal` raises `WalletError("Money must be a Decimal, never a float.")`), fee math uses `RATE.quantize(Decimal("0.01"), ROUND_HALF_UP)`, and an AST rule (`test_no_float_used_for_money`) fails the test suite if any float is used for money.

### Q2.8 How does product deletion work — hard or soft?
**Answer:**
Soft delete. `DELETE /api/products/{id}/` sets `status = INACTIVE` (returns 204) rather than removing the row, so order snapshots (which reference the product) and review history stay consistent. Admins can soft-remove listings to `INACTIVE` as well, always with a mandatory written reason captured in the audit log.

---

## Category 3: Authentication, Authorization & Security

### Q3.1 How is authentication implemented?
**Answer:**
**JWT via `djangorestframework-simplejwt`**:
* **Email is the sole login identifier**, normalized case-insensitively to lowercase; `USERNAME_FIELD = "email"`.
* Login returns an **Access** token (1 day) and a **Refresh** token (7 days).
* **Token rotation + blacklisting** are enabled: every refresh issues a *new* access *and* a *new* refresh, and the old refresh token is blacklisted in the DB.
* Logout (`POST /api/auth/logout/`) blacklists the refresh token server-side immediately.

### Q3.2 How does the mobile app store tokens and survive expirations seamlessly?
**Answer:**
* **Storage:** `expo-secure-store` (iOS Keychain / Android Keystore) — never AsyncStorage.
* **Axios response interceptor** (`src/api/client.ts`): on a `401` (for non-auth endpoints) it runs a **single-flight** (`refreshPromise`) refresh against `/auth/refresh/`, saves the new tokens, and silently retries the original request once. If the refresh itself fails, it clears local tokens and routes to Login. Auth endpoints (`login`, `register`, `refresh`, password routes) are excluded — a 401 there means bad credentials, not expiry.

### Q3.3 How do you prevent a suspended user from logging in?
**Answer:**
The custom `LoginSerializer.validate` rejects a login when `user.profile.account_status != ACTIVE` with `"This account has been suspended."`. Additionally, `IsActiveUser` in the catalog blocks *writes* from suspended accounts, so suspension revokes both new sessions and ongoing activity.

### Q3.4 How does password reset work, and is it secure against user enumeration?
**Answer:**
`POST /auth/password/forgot/` issues a **6-digit code** stored only as a **SHA-256 hash** (never plaintext), valid **15 minutes**, with a **5-attempt** verification cap; issuing a new code invalidates older live codes. The response is **non-enumerating** — identical whether or not the email exists (in `DEBUG` only, the code is echoed as `debug_code`). `POST /auth/password/reset/` validates the code, sets the new password, marks the code used, and invalidates other outstanding codes.

### Q3.5 What password security policies are applied?
**Answer:**
Django's default validators: `UserAttributeSimilarityValidator`, `MinimumLengthValidator(8)`, `CommonPasswordValidator`, `NumericPasswordValidator`. Passwords are hashed with **PBKDF2-SHA256** (never stored in plaintext) by Django's default hasher.

### Q3.6 What rate limiting / throttling is in place?
**Answer:**
DRF throttles: **anonymous 30/min**, **authenticated 120/min**, **login 10/min** (scoped `auth_login`), **password reset 5/min**, **payment initiation 60/min default (15/min in `.env`)**. The rates are overridable via `THROTTLE_*` env vars, and a dedicated test (`test_login_rate_limited_after_burst`) asserts a 429 after a login burst.

### Q3.7 What HTTP/CORS hardening exists?
**Answer:**
Production runs `DEBUG=False` via env; CORS/`ALLOWED_HOSTS` are configured per deployment; media is served by Django with `MEDIA_ROOT` env-overridable. The `SECURE_HTTP` flag is documented to enable HSTS, SSL redirect, and secure cookies behind TLS. The security posture is fully audited in `docs/SECURITY_AUDIT.md`, including a checklist of findings addressed across Prompt 19.

### Q3.8 How are sensitive values protected in logs?
**Answer:**
`auditlog` scrubs a `_SENSITIVE_KEYS` set — `password`, `password_confirmation`, `old_password`, `new_password`, `refresh`, `access`, `token`, `raw_provider_response`, `mobile_money_number` — recursively removing them from the before/after JSON snapshots before a log is written.

### Q3.9 How do you enforce object-level authorization?
**Answer:**
Every write serializer rejects clients setting a `seller` (server derives ownership); chats verify the requester is a `participant` and otherwise return `404` (not 403) to avoid leaking existence; carts are gated by `IsCartOwner` (owner id match or session key match); admin endpoints use DRF's `IsAdminUser`; state-machine actions verify the actor role (buyer/seller/admin/payment).

### Q3.10 Why is there no separate buyer/seller `role` on the User model?
**Answer:**
A deliberate simplification: every account can buy and sell (`Profile.role` is a soft preference used for UI landing screens only, not authorization). This avoids lock-in bugs where a user cannot sell because they registered as a "buyer" — realistic for a second-hand marketplace.

---

## Category 4: Order Lifecycle & State Machine Architecture

### Q4.1 Explain the order state machine and how transitions are controlled.
**Answer:**
All status changes go through `orders/state_machine.py` executed by `orders/services.py`. It is a single source of truth with a strict `(current, action, actor) → next` table and **no direct `PATCH` on status**: only explicit RPC endpoints can act.
**Order level:** `pending_payment --mark_paid(payment/admin)--> paid`; `pending_payment --cancel(buyer)--> cancelled`; `pending_payment --fail_payment(payment)--> payment_failed`; `payment_failed --retry_payment(payment)--> pending_payment`; `payment_failed --cancel(buyer)--> cancelled`; `paid --refund(admin)--> refunded`; `paid --force_cancel(admin)--> cancelled`.
**Item level:** `pending --confirm(seller)--> confirmed`; `confirmed --ship(seller)--> shipped`; `shipped --deliver(seller)--> delivered`; `delivered --complete(buyer)--> completed`. Seller actions require `Order.status == paid`. Invalid transitions raise `TransitionDenied` → 400/403.

### Q4.2 Why model order and item statuses separately, and why not allow generic PATCH?
**Answer:**
The two-tier design reflects reality: one payment, several independent seller fulfillments. Modeling item status separately lets Seller A ship while Seller B is still packing. We expose **action endpoints** (`POST /orders/items/<id>/ship/`, etc.) rather than PATCH status because the state machine must enforce actor roles and preconditions — a generic PATCH would allow arbitrary, invalid jumps (e.g., shipping an unpaid order).

### Q4.3 How is an order created from the cart, and what gets snapshotted?
**Answer:**
`orders/services.create_order_from_cart` runs inside `transaction.atomic()`: it reads the cart line items, snapshots the **seller**, **product**, `product_name`, `product_sku`, `unit_price`, and `quantity` onto `OrderItem` rows (so later changes to a listing can't corrupt a placed order), computes `subtotal`, adds `shipping_cost`, sets `total`, flushes the cart, and writes an `ORDER_CREATE` audit entry.

### Q4.4 How is cancellation handled?
**Answer:**
A buyer may cancel only while `pending_payment` or `payment_failed` (`cancel` action). The service locks the order (`select_for_update`), cascades `item_status = CANCELLED` to every item, writes an `ORDER_TRANSITION` audit entry, and notifies the sellers. Because cancellation is only possible before payment, no funds are involved.

### Q4.5 How is refunding handled, and does the seller lose money?
**Answer:**
Refund is admin-only on a `paid` order (`POST /api/orders/{id}/refund/`). It transitions the order to `refunded`, cascades items to `cancelled`, and notifies sellers. The wallet side uses the ledger's `REFUND` type via `WalletService.refund` when a completed sale is reversed — so a seller who was already credited has those funds removed as a `REFUND`/`DEBIT` entry. (Buyer-side refund of the ClickPesa transaction itself is not automated; we note that as an integration boundary in the docs.)

### Q4.6 What happens when an order is paid — what about stock?
**Answer:**
On `mark_paid` the service, inside the same transaction: (1) marks each `Product.status = SOLD`, (2) deletes matching `CartItem`s so other users can't keep the item in their cart, and (3) projects the seller's pending earnings. Inventory logic is kept simple on purpose: a product becomes `SOLD` once paid rather than auto-decrementing multi-quantity stock, and sellers manage quantities themselves — this is a documented simplification.

### Q4.7 How do you know which buttons to show a user?
**Answer:**
The state machine exposes `available_actions()` for the current `(status, actor)` pair. The seller order screen and buyer screens map those returned action names (`confirm/ship/deliver/complete/cancel/pay/verify`) to UI buttons — so the UI always matches the model's legal transitions.

### Q4.8 How does completing an item propagate to the order?
**Answer:**
Within `transition_item`, after an item reaches `completed`, `_sync_order_status` runs: if the order is `paid` and **all** items are `completed`, the `Order` auto-transitions to `completed`. It also triggers the financial pipeline (`process_completed_sale`) so the seller is credited exactly once per item.

---

## Category 5: Financial Management, Ledger System & Platform Fee

### Q5.1 Why did you use a ledger instead of just increasing a wallet balance?
**Answer:**
Mutating a single integer balance is not auditable and drifts silently. We treat `LedgerTransaction` as the **source of truth** and `Wallet.balance` as a **cached, reconcilable figure**: every financial event inserts an immutable ledger row (`credit`, `debit`, `withdrawal`, `refund`, `adjustment` — plus informational `payment` and `platform_fee`), and `WalletService.reconcile_balance` recomputes the cached balance as the sum of completed balance-affecting rows inside a transaction. Drift is therefore impossible by construction.

### Q5.2 How exactly is the 6% platform commission calculated and posted?
**Answer:**
In `WalletService.process_completed_sale(order_item)`, executed when a sale item is completed, all inside `transaction.atomic()`:
1. Lock the seller wallet: `Wallet.objects.select_for_update().get_or_create(user_id=seller_id)`.
2. `fee = (line_total * Decimal("0.06")).quantize(Decimal("0.01"), ROUND_HALF_UP)`.
3. `net = (line_total - fee).quantize(Decimal("0.01"))`.
4. Insert a `PLATFORM_FEE` row (`-fee`) and a `CREDIT` row (`+net`) linked by `reference="order-item:<pk>"`.
5. Reconcile the cached balance and mark the product `SOLD` when appropriate.
**Idempotency:** a DB `UniqueConstraint(order_item, type)` prevents a second `PLATFORM_FEE`/`CREDIT` pair even under double-invocation.

### Q5.3 How do you prevent race conditions, double-spending, or overdrafts?
**Answer:**
Three layers:
1. **Pessimistic row locks** — `select_for_update()` on wallets, orders, and payments so concurrent transactions serialize.
2. **Server-side validation** — `reconcile_balance(user) >= amount` before any debit/withdrawal.
3. **DB constraint backstop** — `CheckConstraint(balance >= 0)` means even a logic bug cannot create a negative balance; the DB aborts the transaction with an integrity error.

### Q5.4 How are withdrawals designed so money can't be lost?
**Answer:**
`request_withdrawal` performs a **hard-debit reservation**: the request row *and* a completed `WITHDRAWAL` ledger entry (negative amount) are written together in one atomic block, so funds leave the spendable balance immediately and `InsufficientBalance` rolls everything back. On the admin transitions to `failed` or `rejected`, a `REFUND` ledger entry reverses the exact amount in the same transaction. Only `is_staff` can transition a withdrawal, and the row is locked with `select_for_update`. The minimum withdrawal is **500 TZS** (`CheckConstraint(amount >= 500)`), and ending the payout (ClickPesa `POST /payouts/create-mobile-money-payout`) is best-effort — it never blocks the status change.

### Q5.5 How is "pending earnings" computed?
**Answer:**
`WalletService.pending_earnings` is read-only: it projects `unit_price * quantity * (1 - 0.06)` for `OrderItem`s whose `Order.status == PAID`, excluding already `COMPLETED`/`CANCELLED` items. It deliberately *does not* write to the wallet — actual funds are credited only when the buyer completes the item.

### Q5.6 What balance summaries can a user see?
**Answer:**
`WalletService.balance_summary(user)` returns `{balance, total_earnings (sum of CREDIT), total_withdrawn (absolute sum of WITHDRAWAL)}`, served by `GET /api/wallet/balance/`, `/wallet/transactions/` (filterable by type/date), and `/wallet/pending-earnings/`. All wallet write logic lives behind service functions — there is no public endpoint that mutates a balance.

---

## Category 6: Payment Gateway Integration (ClickPesa & Webhooks)

### Q6.1 Walk through the ClickPesa payment flow.
**Answer:**
1. Buyer checks out → `Order` created in `pending_payment`; the Payment screen posts `{order_id, phone_number}` (Tanzanian `^255\d{9}$`) to `POST /api/payments/initiate/`.
2. Backend generates an access token (Bearer JWT, **cached for 1 hour**, `TOKEN_TTL_SECONDS = 60*60`), creates a `Payment` row (`external_reference = "RH" + first-10-char order number + attempt digit`), then sends `POST /payments/initiate-ussd-push-request` with amount, `TZS`, the `orderReference`, and a `webhookUrl` = `CLICKPESA_WEBHOOK_BASE_URL` + `/api/clickpesa/webhook/`.
3. ClickPesa triggers a **USSD push** on the buyer's phone for the Mobile Money PIN.
4. On confirmation, ClickPesa posts an async webhook; a checksum-verified `PAYMENT RECEIVED` event moves the order to `paid`, marks products `SOLD`, notifies buyer/seller, and writes audit entries.

### Q6.2 How do you verify a webhook is genuinely from ClickPesa (anti-forgery)?
**Answer:**
Canonical **HMAC-SHA256 checksum** verification in `payments/checksum.py`:
1. **Canonicalize** — recursively sort all JSON object keys at every level.
2. **Compact-serialize** — `json.dumps(..., separators=(",", ":"))`.
3. **Sign** — HMAC-SHA256 hex digest using the shared secret (`CLICKPESA_WEBHOOK_SECRET`, the `CHK...` key).
4. **Compare** with `hmac.compare_digest` (timing-safe). Any missing/mismatched checksum → HTTP `403` immediately. Both top-level `checksum` and nested `data.checksum` variants are handled.

### Q6.3 What fields do you double-check before marking an order paid?
**Answer:**
Only recognized events (`PAYMENT RECEIVED`, `PAYMENT FAILED`, `PAYMENT CANCELLED` — names normalized) are processed; resolution falls back `orderReference → paymentReference → gateway transaction id`; processing is **idempotent** (a final-state payment is a no-op); and if the gateway reports a `collectedAmount` that **mismatches the order total**, the payment is marked `FAILED` with reason `"Amount mismatch"` and the order is **left untouched** — we never auto-mark paid on a wrong-amount event.

### Q6.4 What if the webhook is dropped or never arrives?
**Answer:**
Two fallbacks:
1. **Manual verify** — the app has a "Verify payment" button calling `POST /api/payments/<order_id>/verify/`, which queries ClickPesa server-to-server (`GET /payments/{orderReference}`) and syncs state.
2. **Reconciliation command** — `python manage.py reconcile_payments [--window-minutes 5] [--max 50]` (cron-able) finds `PENDING` payments older than the window, asks the gateway, and applies terminal states exactly as the webhook would — with `select_for_update` and the same amount-mismatch guard.

### Q6.5 How are payments idempotent across retries and concurrent callbacks?
**Answer:**
Only one `PENDING` attempt is allowed per order (previous pending attempts are `EXPIRED` on retry), the webhook/verify/reconcile paths share `_mark_paid_if_possible` which is a no-op once the order is `paid`, the payment row is locked with `select_for_update`, and the order transition itself is locked too. So a duplicate webhook or a race between webhook and manual verify cannot double-charge or double-transition.

### Q6.6 How do payouts to sellers work?
**Answer:**
When admin completes a withdrawal, `WithdrawalPayoutService.attempt(request)` best-effort calls ClickPesa `POST /payouts/create-mobile-money-payout`; the result (`payout_reference`, `payout_status`, `payout_message`) is recorded on the request without blocking the status transition. If payouts are disabled or credentials absent (`CLICKPESA_PAYOUTS_ENABLED=False`), it records `payout_status="UNAVAILABLE"` — this keeps the demo usable without a live payout account.

### Q6.7 Why TZS and the specific phone-number validation?
**Answer:**
The target market is Tanzania — ClickPesa supports Tigo Pesa, M-Pesa, and Airtel Money in TZS. The backend validates `^255\d{9}$` (no `+`) so only a well-formed Tanzanian subscriber number reaches the gateway, and the mobile app auto-normalizes `0XXXXXXXXX` → `255XXXXXXXXX` for usability.

---

## Category 7: Real-Time Communication & Messaging Architecture

### Q7.1 How is the in-app chat implemented, and why polling instead of WebSockets?
**Answer:**
Chat is a REST service (`chat` app). The conversation screen **polls `GET /api/chats/{id}/messages/` every 5 seconds** while focused and shows new messages using a load-older pagination pattern. Choices:
1. **Infrastructure simplicity** — WebSockets would require an ASGI server, a Redis channel layer, and separate WebSocket auth; polling runs on standard WSGI/Gunicorn, HTTP, and JWT headers with zero extra moving parts.
2. **Fit to the use case** — marketplace negotiation is asynchronous and low-frequency; 5-second polling is imperceptible for this UX while avoiding protocol overhead.
This is documented as a deliberate trade-off, with Django Channels listed as a future enhancement. Live typing indicators are absent by design.

### Q7.2 How do you guarantee chat privacy and prevent abuse?
**Answer:**
* Conversations are **product-scoped** (tied to a `product`) or **direct** between two users; **self-chats are rejected** server-side; get-or-create reuses an existing thread for the same two participants + product.
* Every endpoint verifies the requester is a **participant**; non-participants receive a **404** for message history (no information disclosure).
* Phone numbers/personal emails are never exposed on public listings — contact happens inside the app.
* Messages are stripped and **max 4000 chars**; unread counts and `mark-read` are per conversation.

### Q7.3 How are read/unread states handled?
**Answer:**
`Message.is_read` defaults false; `POST /api/chats/{pk}/read/` marks the other participant's messages read and returns `{marked_read: n}`. This drives the unread badges in the conversation list, while notifications (`type=new_message`) provide the in-app alert.

---

## Category 8: Audit Logging, Admin Moderation & Reporting

### Q8.1 Explain the audit log design.
**Answer:**
The `auditlog` app has a single write path: `AuditLogService.log(actor, action, target, before, after, request)`, capturing actor, standardized **action code (25 values** — e.g. `auth.login`, `payment.success`, `admin.product_remove`), target model/id, description, client **IP** (`X-Forwarded-For` first hop, else `REMOTE_ADDR`), and before/after JSON snapshots. It is:
* **Append-only** — no update/delete endpoints exist (tests assert `405` for destructive methods and that even admins cannot append via API).
* **Non-blocking/best-effort** — a logging failure never rolls back the primary business transaction.
* **Scrubbed** — sensitive keys (`password`, `token`, `mobile_money_number`, `raw_provider_response`, …) are stripped recursively before storage.

### Q8.2 What does the admin dashboard expose?
**Answer:**
`GET /api/admin/dashboard/`: user totals split into `{active, suspended}`, product `{total, active}`, `orders_by_status` grouping, total order value, **transaction volume** (sum of successful `Payment` amounts), **platform fees collected** (absolute sum of `PLATFORM_FEE` rows), withdrawals pending/processing/completed, failed-payment count, and a `recent_activity` feed. `GET /api/admin/reports/summary/?days=30` (clamped 1–365) aggregates, via **single `TruncDate` database queries**, daily transaction volume, fee revenue over time, and new users per day.

### Q8.3 How are users and products moderated?
**Answer:**
* **Users:** search, detail (with `product_count`, `order_count`, `sold_count`, `wallet_balance`), edit, `suspend`/`activate` (returning suspended accounts to login-blocked state), and delete. Admin accounts are protected from deletion/self-delete.
* **Products:** list all incl. inactive, and `POST /api/admin/products/{pk}/remove/` with a **required `reason` (max 500 chars)** soft-deletes to `INACTIVE` and records the reason in the audit log.
* Every admin mutation writes an audit entry (e.g. `admin.user_suspend`, `admin.product_remove`, `admin.category_update`).

### Q8.4 Why is the audit log read-only through the API?
**Answer:**
Immutability is the entire point of an audit trail: if a log could be edited or deleted, it would be worthless as evidence. We therefore expose only `GET /api/audit-logs/` (with filters actor/action/target_model/created_after/created_before) and `GET /api/audit-logs/{pk}/`, protect admin add/change/delete permissions, and enforce the invariant in tests.

---

## Category 9: Mobile Client (React Native / Expo) & UX Architecture

### Q9.1 Describe the mobile app's state-management architecture.
**Answer:**
React **Context + custom hooks** — deliberately avoiding Redux boilerplate for a project this size:
* `AuthContext` (reducer with `loading | authenticated | unauthenticated`) manages token bootstrap, sign-in, sign-up, sign-out and validates the session on startup via `/users/me/`.
* `FavoritesContext` keeps a `ReadonlySet<number>` of favorite ids, loaded from `GET /favorites/`, with optimistic add/remove and rollback on failure.
* `ToastContext` provides the global, non-blocking success/error/info banner (Animated fade, pointerEvents none) — the app never uses `Alert.alert`.
* Custom hooks encapsulate screen logic: `useProductFeed` (infinite scroll + pull-to-refresh), `useDebouncedValue` (400 ms), `useCategories`, `useOrdersList`, `useUnreadNotificationCount`.

### Q9.2 How does the product feed achieve pagination and responsiveness?
**Answer:**
`useProductFeed` serializes `{filters, search, ordering}` into a `paramsKey` that retriggers the initial load; it follows the DRF `next` URL for infinite scroll, uses a `seqRef` to guard against stale responses (race between a refresh and a param change), and distinguishes `initial` (skeleton) vs `refresh` (keep list + `RefreshControl`) loading states. Product cards render a skeleton while loading, 20-item pages come from the server, and pull-to-refresh/reload is native `RefreshControl`.

### Q9.3 How are the search and filtering UX handled?
**Answer:**
The search input debounces queries by **400 ms** (`useDebouncedValue`), preventing an API call per keystroke. A `Filters` **modal** collects category, condition, min/max price, and location and returns them via route params, which are merged into the feed hook. The screenshot-ready triage of Home (category chips + newest feed), Search (keyword + filters), and Product Detail (image carousel, favorites, chat, add-to-cart, reviews) covers the whole browse path.

### Q9.4 How does the payment user experience work on the app?
**Answer:**
`PaymentScreen` normalizes the phone number (`0XXXXXXXXX` → `255XXXXXXXXX`), calls `POST /payments/initiate/`, then **polls `GET /payments/{orderId}/status/` on an escalating back-off schedule `[3000, 5000, 8000, 10000, 15000]` ms** with a success modal, and offers a manual **"Verify payment"** button that triggers the server-side `POST /payments/{orderId}/verify/` gateway check. The app never declares success itself — it only reflects what the backend has verified.

### Q9.5 What polish/Easter-egg features support the demo?
**Answer:**
* **QR codes for orders** — the order screen renders `reusehub-order:{orderId}` via `react-native-qrcode-svg` and the Scan screen reads it back with `expo-camera`, jumping straight to the order — a clean way to demonstrate buyer/seller hand-off live.
* **Role-aware home tab** — the initial tab is chosen from role (`ADMIN → Admin`, `SELLER → Selling`, else Home).
* **Hermes-safe `formatPrice`** — manual thousands grouping (`\B(?=(\d{3})+(?!\d))`) because Hermes' Intl support is incomplete; `formatRelativeTime` for "5m ago" style timestamps.

### Q9.6 How do notifications surface in the app?
**Answer:**
`GET /api/notifications/` (paginated, own-only), `POST .../read/`, `POST .../read-all/`, and the **unread-count badge** (`GET /api/notifications/unread-count/`), refetched on screen focus. Notifications deep-link by `related_type` (`order`, `conversation`, `withdrawalrequest`) to the matching screen. Notification types: `order_update`, `payment_result`, `new_message`, `withdrawal_update`, `system`.

### Q9.7 How is the mobile app built for distribution?
**Answer:**
Expo Go for instant demos; **EAS Build** with three profiles in `eas.json`: `development` (development client, internal, local API URL), `preview` (**installable Android APK** for demo distribution), and `production` (**signed app bundle** with `autoIncrement` versioning). `app.json` pins `sdkVersion: "54.0.0"`. iOS production builds require a paid Apple Developer account — a documented limitation; iPhone demos use Expo Go.

---

## Category 10: Testing, Quality Assurance, Concurrency & Deployment

### Q10.1 Describe the overall testing strategy.
**Answer:**
* **Backend — pytest (316 tests)** across all 13 apps: model constraints, API permissions, JWT/suspension/throttling, state-machine transitions (every edge), payment webhooks, ledger reconciliation, wallet/withdrawal concurrency, chat, reviews, notifications, admin, and audit log. `conftest.py` disables the throttle limit except in dedicated throttle tests and forces `CLICKPESA_PAYOUTS_ENABLED=False`.
* **End-to-end journey tests** — `payments/test_journeys.py` runs the full buyer journey (register → list → cart → checkout → pay → confirm → ship → deliver → complete → ledger credit → withdraw) and seller journey over real HTTP endpoints.
* **Frontend — Jest (7 test files)** for API wrappers and the client interceptors using `axios-mock-adapter`; plus **TypeScript strict (`tsc --noEmit`), ESLint, Prettier** checks.

### Q10.2 How do you test the financial-critical and security-critical parts?
**Answer:**
* `payments/test_financial_consistency.py` and `wallet/tests.py` exercise ledger reconciliation and **concurrency** — e.g. parallel withdrawal requests in threads verifying the final balance and ledger sums stay consistent and never negative.
* A **no-float-for-money AST test** (`test_no_float_used_for_money`) scans the codebase and fails if `float` is used in money contexts.
* `accounts` tests cover token expiry, refresh rotation/blacklisting, suspension blocking login, and login burst throttling (429).
* `auditlog` tests assert append-only behavior, sensitive-key scrubbing, and that even admins cannot modify logs.

### Q10.3 What does the state-machine test coverage look like and why does it matter?
**Answer:**
`orders/test_state_machine.py` has 27 tests covering every valid transition and every invalid one: wrong actor, wrong precondition (e.g., seller shipping an unpaid order), illegal jumps, and idempotency of repeated actions. Because the order flow sits between a buyer's money and a seller's goods, exhaustive legal/illegal transition coverage is the single most valuable assurance in the project.

### Q10.4 How is the application deployed and run in production?
**Answer:**
* **Docker Compose** — `docker-compose.yml` defines `backend` (Gunicorn via `backend/Dockerfile`) and `db` (PostgreSQL); static files served by **WhiteNoise** through Gunicorn; media served by Django.
* **Render** — `render.yaml` provides hosted deployment configuration (`reusehub-backend.onrender.com`-style URLs), with `render-build.sh`/`render-start.sh`.
* **Bare VPS** — documented as `gunicorn config.wsgi:application` in `docs/DEPLOYMENT.md`.
* Production posture: `DEBUG=False`, restricted `ALLOWED_HOSTS`/CORS, `SECURE_HTTP=True` (HSTS, SSL redirect, secure cookies) behind TLS.

### Q10.5 How do you handle webhook delivery in a deployed environment?
**Answer:**
The webhook endpoint is public (`AllowAny`) and proves authenticity via the HMAC checksum, so no bearer token is needed. The `CLICKPESA_WEBHOOK_BASE_URL` env var is set to the public deployment URL (e.g. `https://reusehub-backend.onrender.com`) so the gateway hits the right host. In local testing, `NGROK_PUBLIC_URL` supplies the tunnel URL, `ALLOWED_HOSTS` includes the ngrok subdomain, and the ClickPesa dashboard callback URL is pointed at `${URL}/api/clickpesa/webhook/`.

### Q10.6 What is the backup strategy?
**Answer:**
Documented in `docs/BACKUP_STRATEGY.md`: scheduled **PostgreSQL `pg_dump` snapshots** (database) plus media directory backups, with a documented restore procedure. It is a manual/scheduled local strategy rather than enterprise point-in-time recovery — WAL archiving is listed as future work.

### Q10.7 What quality gates run before merging changes?
**Answer:**
Backend: `python manage.py check`, `pytest -q`, `ruff check .`, `python manage.py makemigrations --check`. Mobile: `npm test`, `npm run typecheck`, `npm run lint`, `npm run format:check`. These are the documented "done" definition in the README.

---

## Category 11: Known Limitations, Scope & Challenge ("Gotcha") Questions

### Q11.1 Is ReuseHub production-ready?
**Answer (honest):**
For a **fielded marketplace** we would not claim production-ready. It is a complete, tested final-year project. Known, documented boundaries (`docs/PROJECT_STATUS.md`): chat uses polling not WebSockets; notifications are in-app only (no FCM/APNs push); iOS production build needs a paid Apple account; ClickPesa payments are live-gateway (no sandbox, so the offline demo uses a documented mark-paid path); image storage is local Django-backed media (no S3); backups are scheduled dumps, not PITR. Each is a named future enhancement.

### Q11.2 What if an attacker posts a forged "payment success" webhook?
**Answer:**
They can't get past verification: the payload must carry an **HMAC-SHA256 checksum** computed with the shared secret over the canonicalized (sorted, compact) JSON; `hmac.compare_digest` must match, else we return `403` before any state change. An attacker without the secret cannot forge a valid signature.

### Q11.3 What happens if two buyers race to pay for the same low-quantity product?
**Answer:**
Order creation is serialized on the order row (`select_for_update`); payment path is serialized on the payment/order rows and gated by the state machine (`pending_payment → paid` via `mark_paid(payment)` only), and a DB `UniqueConstraint` prevents duplicate ledger credits. The main simplification is that product stock is a seller-managed `quantity` and the status flips to `SOLD` on payment — it is not a decrementing inventory system (documented; future work).

### Q11.4 What is the most dangerous failure the system protects against, and how?
**Answer:**
**Money drift / double-credit.** Guard rails: immutable double-entry ledger as source of truth with `Wallet.balance` reconciled from it; `UniqueConstraint(order_item, type)` making the fee+credit post idempotent; `CheckConstraint(balance >= 0)` as the DB backstop; `select_for_update()` across wallets, orders, and payments; and concurrent financial tests in `test_financial_consistency.py` and `wallet/tests.py`.

### Q11.5 Why do you return 404 (not 403) for chat endpoints non-participants query?
**Answer:**
Returning 404 hides the existence of a conversation between two other users (an information-disclosure control). If we returned 403, a caller would learn that a thread with that ID exists; 404 reveals nothing.

### Q11.6 Why 1-day access tokens and 7-day refresh tokens?
**Answer:**
It balances security and UX: short-lived access tokens shrink the window a stolen token is usable, and although the refresh token is longer-lived, it is rotated on every use and blacklisted on logout — so a reused/stolen refresh token causes a mismatch and gets rejected, which is exactly the SimpleJWT rotation model's purpose.

### Q11.7 How did you build this project—what was the process?
**Answer:**
It was built incrementally across **20 prompts**, each an architecture stage: project setup → accounts/JWT → catalog models → catalog API → mobile skeleton → marketplace UI → cart/orders → order state machine → payments → wallet/ledger → mobile marketplace → withdrawals → chat → notifications → reviews → admin panel → audit log → full-stack polish → security & consistency testing → production readiness. `docs/ARCHITECTURE.md` records the prompt-by-prompt history; `docs/PROJECT_STATUS.md` records verified behavior and honest scope notes.

### Q11.8 What is your favourite part of the project and what would you do next?
**Answer (frame it yourself):**
Good answers: the **state machine + double-entry ledger** because they are where engineering rigor matters (financial correctness), or the **HMAC-verified webhook + reconciliation** design. Next steps should mirror the roadmap: WebSockets chat, push notifications, S3/CDN media, PITR backups, captcha on auth, and mobile E2E with Detox/Playwright.

### Q11.9 Why TZS only — no USD or multi-currency?
**Answer:**
ClickPesa is a Tanzanian mobile-money gateway operating in **TZS**; the project targets the Tanzanian second-hand market first. Multi-currency support would require exchange-rate handling and additional payment partners — deliberately out of scope but the architecture (currency as a `CLICKPESA_CURRENCY` env string, Decimal amounts) makes it additive later.

### Q11.10 Isn't a 6% platform fee arbitrary?
**Answer:**
6% is a single constant (`PLATFORM_FEE_RATE = Decimal("0.06")`) in `wallet/services.py`, easily configurable, and sits in a realistic range for marketplace commissions (platforms commonly range ~5–15%). It also produces round, demonstratable math in the demo (e.g., a 10 000 TZS sale → 600 TZS fee, 9 400 TZS to the seller).

### Q11.11 How do you prove the audit log wasn't tampered with?
**Answer:**
We enforce append-only at the data layer (no update/delete endpoints, no admin mutation permissions, tested invariants), which materially raises the cost of tampering. Cryptographic hash-chaining of log entries (a hash pointer per row) is a known hardening we list as future work — honest note that today's protection is access/API-level, not cryptographic.

### Q11.12 Why did you write `conftest.py` to disable throttling in tests?
**Answer:**
So ordinary tests measure functional behavior, not network shaping. Throttling itself is then tested deliberately in `LoginThrottleTests`, which re-applies a strict rate via `override_settings` and asserts a `429` after a burst — the throttles are both tested and not allowed to dominate unrelated suites.

---

## Quick Reference Metrics & Tech Specs Cheatsheet

| Metric / Parameter | Value (from current code) |
|---|---|
| **Backend framework** | Django 6.1 / Django REST Framework (Python 3.12), 13 apps |
| **Frontend framework** | Expo **SDK 54** / React Native 0.81.5 / React 19.1.0 / TypeScript strict |
| **Database** | PostgreSQL 14+ (production), SQLite (local default via `USE_SQLITE`) |
| **Database size** | 31 tables, clean migrations from zero |
| **Authentication** | SimpleJWT — Access **1 day**, Refresh **7 days**; rotation + blacklisting; email-only login |
| **Platform commission** | **6%** (`Decimal("0.06")`), fee `ROUND_HALF_UP` to 0.01, net = line total − fee |
| **Payment gateway** | ClickPesa USSD-push collection + payouts, **TZS**, phone `^255\d{9}$` |
| **Webhook security** | HMAC-SHA256 on canonicalized (sorted/compact) JSON, `compare_digest`, amount-mismatch guard |
| **Gateway token cache** | 1 hour (`TOKEN_TTL_SECONDS`) |
| **Chat architecture** | REST + 5-second client polling; message cap **4000 chars** |
| **Audit log** | 25 action codes; append-only; sensitive-key scrubbing; IP captured |
| **Throttles** | anon 30/min, user 120/min, login 10/min, password reset 5/min, payment initiate 60/min (15/min in `.env`) |
| **Image upload** | max **5 MB**; `.jpg/.jpeg/.png/.webp/.gif`; MIME + Pillow content verify |
| **Password reset code** | 6-digit, SHA-256 hashed, 15-min TTL, 5 attempts, non-enumerating |
| **Cart merge cap** | quantity up to **100** per identical line |
| **Withdrawal minimum** | **500 TZS** (DB constraint); providers mpesa/tigo_pesa/airtel_money/halopesa |
| **Order number** | `uuid4().hex[:16].upper()`; payment ref `RH` + order[:10] + attempt digit |
| **Catalog pagination** | page size 20, max 100 (DRF `next`-based) |
| **Backend test suite** | **316 pytest tests** incl. journey + financial-concurrency + no-float AST rule |
| **Mobile quality** | Jest (7 test files), `tsc --noEmit`, ESLint, Prettier |
| **Deployment** | Docker Compose (Gunicorn + PostgreSQL), WhiteNoise, `render.yaml`, EAS profiles preview/production |
| **Deadline/scope guard** | Final-year project, not a production marketplace (see `docs/PROJECT_STATUS.md`) |