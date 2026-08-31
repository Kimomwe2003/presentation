# ReuseHub — Architecture & Development Standards

Living reference document for the ReuseHub project. Update it as the system evolves.

## Monorepo layout

```
reusehub/
├── backend/        # Django project root (config/ settings, manage.py)
│   ├── config/     # Django project package (settings, urls, wsgi, asgi)
│   ├── core/       # Placeholder app (custom user + shared helpers, future)
│   ├── .env.example
│   ├── requirements.txt
│   ├── pytest.ini
│   └── pyproject.toml   # ruff config
├── mobile/         # Expo / React Native (TypeScript) app
│   ├── src/
│   │   ├── api/            # Axios client (EXPO_PUBLIC_API_URL), token storage, auth + catalog calls
│   │   ├── components/     # Reusable UI: Button, TextInput, Card, ProductGrid, skeletons, carousel
│   │   ├── context/        # AuthContext (session), ToastContext (error surface), FavoritesContext
│   │   ├── hooks/          # useProductFeed (pagination), useCategories, useDebouncedValue
│   │   ├── navigation/     # RootNavigator (auth gate), AuthStack, AppStack (bottom tabs)
│   │   ├── screens/        # auth/, marketplace/, chat/, profile/
│   │   └── theme.ts        # Design tokens (colors, spacing, radii, typography)
│   ├── .env.example
│   ├── app.json
│   ├── jest.config.js
│   ├── eslint.config.js
│   └── package.json
└── docs/           # Design & architecture documentation
```

## Backend (Django + DRF)

- **Framework**: Django + Django REST Framework (DRF)
- **Auth**: `djangorestframework-simplejwt` (access + refresh tokens)
- **DB**: PostgreSQL (via `psycopg2-binary`)
- **Config**: `django-environ` — every secret comes from environment variables; `.env` is never committed
- **Filtering**: `django-filter`
- **CORS**: `django-cors-headers`
- **Media**: Pillow (image uploads)

### Planned Django apps (from Master Plan Part A.2)

| App | Purpose | Status |
| --- | --- | --- |
| `core` | Placeholder app — shared helpers/utilities, base mixins | Scaffolded (placeholder) |
| `accounts` | Custom user, profile, JWT auth (register/login/refresh/logout), `/api/users/me/` | **Built (Prompt 02)** |
| `catalog` | Category, Product, ProductImage, Favorite models + admin (no API yet) | **Models built (Prompt 03)** |
| `categories` | Product categories | Part of `catalog` |
| `products` | Product listings, product images, product reviews | Part of `catalog` (reviews later) |
| `cart` | Cart & cart items | **Built (Prompt 07)** |
| `orders` | Orders & order items | **Built (Prompt 07)** |
| `payments` | Payment records / ClickPesa integration | **Built (Prompt 09)** |
| `wallet` | Wallet + ledger (source of truth) for seller earnings | **Built (Prompt 10)** |
| `withdrawals` | Withdrawal requests & admin processing | **Built (Prompt 12)** |
| `chat` | Conversations & messages between users | **Built (Prompt 13)** |
| `notifications` | In-app notification list (generic FK, unread badge) | **Built (Prompt 14)** |
| `reviews` | Product/seller reviews & ratings, completed-purchase restriction | **Built (Prompt 15)** |
| `adminpanel` | Staff-only dashboard & moderation API (`/api/admin/`), no new models | **Built (Prompt 16)** |
| `auditlog` | Append-only audit trail + staff reporting (volume/fees/new users) | **Built (Prompt 17)** |

> **Prompt boundary**: catalog REST endpoints are deferred to Prompt 04.

## Catalog models (Prompt 03)

- **Category**: name, slug (unique), optional `parent` self-FK for subcategories, `is_active`, timestamps.
- **Product**: `seller` (FK User), `category` (FK Category, SET_NULL), name, description, price (Decimal),
  condition (`NEW/LIKE_NEW/GOOD/FAIR/USED`), quantity (default 1), location, status
  (`DRAFT/ACTIVE/SOLD/INACTIVE`, default `DRAFT`), timestamps.
  - `db_index` on `seller`, `category`, `status`.
  - DB `CheckConstraint`s: `price > 0`, `quantity >= 0` (verified via `pg_constraint`).
  - `clean()` mirrors the constraints for friendly errors.
- **ProductImage**: `product` (FK, CASCADE), `image` (ImageField), `is_primary`, `order`.
  - Stored under `MEDIA_ROOT/products/<product_id>/<uuid>.<ext>`.
  - Validators (model layer, run in `full_clean`/serializers): allowed extensions
    (jpg/jpeg/png/webp/gif), allowed MIME types, max 5 MB, plus a Pillow decode check.
    `save()` calls `full_clean()` so direct ORM saves are validated too.
- **Favorite**: `user` (FK), `product` (FK), `UniqueConstraint(user, product)` blocks duplicates.

All four models are registered in Django admin (list_display / list_filter / search_fields).

## Cart & orders (Prompt 07)

- **Money**: prices stay `Decimal` end-to-end. `catalog.Product.effective_price()` returns the
  current price; cart line totals and order totals are `Decimal` and formatted with a
  thousands-separator helper (`core.utils.int_to_pretty`).
- **Cart**: one cart per logged-in user (`owner` OneToOne). Anonymous carts are identified by
  `session_key` instead, with a DB `CheckConstraint` requiring exactly one of `owner`/`session_key`.
  Anonymous carts expire (soft-delete check on `expires_at`, 30-day TTL).
- **CartItem**: `cart`, `product`, `quantity` (1–100), `attributes` (JSON, for future variants).
  A partial unique constraint blocks duplicate `(cart, product)` rows when no attributes are set.
- **Order**: `order_number` (auto-generated), `buyer` (FK User, was `user`; renamed in Prompt 08),
  `status`, `payment_method`, `shipping_address` (JSON), `subtotal`/`shipping_cost`/`total`
  (Decimal), `placed_at`. `OrderItem` snapshots `product_name`/`unit_price`/`quantity`/`attributes`
  so order history survives product edits or deletion.
- **Anonymous cart merge**: when an authenticated user places an order, any anonymous cart items
  (matched by session) are merged into their cart first; quantities combine up to 100, and the
  anonymous cart is deleted.
- **Order creation** happens in a single transaction (`orders/services.create_order_from_cart`):
  items snapshot from the cart, the cart is flushed, and the `Order` + `OrderItem` rows are created.

## Order lifecycle & state machine (Prompt 08)

- **Multi-seller decision (final)**: one `Order` is a buyer's payment envelope that may contain
  items from several sellers. `Order.status` holds the *payment/envelope* state;
  `OrderItem.item_status` holds a per-seller *fulfillment* state (subset of the order states:
  `pending/confirmed/shipped/delivered/completed/cancelled`). Each seller manages their own items
  independently; when every item is `completed` the envelope auto-moves to `completed`.
- **Order.status choices**: `pending_payment`, `paid`, `confirmed`, `shipped`, `delivered`,
  `completed`, `cancelled`, `payment_failed`, `refunded` (default `pending_payment`; the old
  `pending` value was data-migrated to `pending_payment`).
- **Single transition service**: all status changes go through
  `orders/services.py` → `orders/state_machine.py`. The state machine owns the
  `(current_status, action) → next_status` table plus an object-level actor check per transition.
  No view writes `status`/`item_status` directly and there is **no generic PATCH** on status.
- **Allowed transitions**
  - `pending_payment → paid` (payment provider/`actor="payment"` — Prompt 09; admins via
    `POST …/mark-paid/` until then).
  - `pending_payment → cancelled` (buyer only — the sole pre-payment cancel).
  - `pending_payment → payment_failed` (payment), `payment_failed → pending_payment` (retry).
  - `paid → refunded` / `paid → cancelled` (admin force only).
  - Item: seller `pending → confirmed → shipped → delivered`; buyer `delivered → completed`
    (buyer confirms receipt — this is the chosen DELIVERED policy).
  - Item/order `cancelled` cascades from the order-level cancel/refund flows (admin or buyer
    pre-payment); there is no public item-level cancel endpoint.
- **Preconditions**: fulfillment item transitions require `order.status == paid`; an unpaid order
  cannot be confirmed/shipped/delivered. Buyer completion requires `delivered`.
- **Errors**: disallowed transitions return `400` (wrong state/precondition) or `403` (wrong role);
  non-parties get `404` so order existence is not leaked.
- **Indexes** (Prompt 08): `Order.status`, `Order.buyer`, `OrderItem.seller`, `OrderItem.item_status`.
- **Payment note**: real payment (Prompt 09) will call the same service with `actor="payment"`;
  nothing in this prompt integrates a gateway.

### Cart & orders API (Prompt 08)

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/cart/` | Any | Current cart (creates one for anonymous sessions) |
| GET/POST | `/api/cart/items/` | Any (owner-scoped) | List / add items |
| PATCH/DELETE | `/api/cart/items/<id>/` | Any (owner-scoped) | Update quantity / remove item |
| GET/POST | `/api/orders/` | Bearer | Buyer's orders / create order from cart |
| GET | `/api/orders/<id>/` | Bearer | Buyer's order detail |
| POST | `/api/orders/<id>/cancel/` | Bearer | Buyer cancels (pre-payment only) |
| POST | `/api/orders/<id>/mark-paid/` | Bearer (admin) | Manual/test trigger until Prompt 09 |
| POST | `/api/orders/<id>/refund/` | Bearer (admin) | Force refund a paid order |
| GET | `/api/orders/selling/` | Bearer | Seller's incoming orders |
| GET | `/api/orders/selling/<id>/` | Bearer | Seller's order detail (their items only) |
| POST | `/api/orders/items/<id>/confirm/` | Bearer (item seller) | Accept item |
| POST | `/api/orders/items/<id>/ship/` | Bearer (item seller) | Mark shipped |
| POST | `/api/orders/items/<id>/deliver/` | Bearer (item seller) | Mark delivered |
| POST | `/api/orders/items/<id>/complete/` | Bearer (buyer) | Confirm receipt |

Serializers expose `available_actions` per order and per item (computed against the requesting
user) so the mobile UI only renders valid buttons. Sellers only see their own item lines in the
`/selling/` views.

## Wallet, ledger & platform fee (Prompt 10)

- **Ledger is the source of truth (chosen approach)**: every balance change is a
  `LedgerTransaction` row. `Wallet.balance` is a *cached/reconciled* value — it is recomputed as
  the sum of the user's `COMPLETED`, balance-affecting ledger rows inside the same transaction that
  writes those rows (`wallet.services.reconcile_balance` + `WalletService`), so it can never
  silently drift from the ledger.
- **Signed amounts**: positive = money added, negative = money removed. Balance-affecting types
  (summed into `balance`): `credit`, `debit`, `withdrawal`, `refund`, `adjustment`. Informational
  accounting entries excluded from the sum: `payment` (buyer paid) and `platform_fee` (the net
  `credit` already reflects the fee).
- **6% platform fee**: on the `delivered → completed` transition
  (`orders/services.transition_item` → `WalletService.process_completed_sale`) the service, in one
  `transaction.atomic()`, locks the seller's wallet (`select_for_update`), creates a `platform_fee`
  row (`-fee`) and a `credit` row (`net = line_total - fee`), then reconciles the cached balance.
  All math is `Decimal` (`fee = (line_total * Decimal("0.06")).quantize(0.01, ROUND_HALF_UP)`).
- **Idempotency & concurrency**: re-processing an already-credited item is a no-op — the service
  checks for an existing row, and a unique `(order_item, type)` constraint is a second, DB-level
  guarantee. Concurrent completions serialize on the wallet row lock.
- **Negative-balance guard**: `WalletService.debit` (used by withdrawals in Prompt 12) verifies
  sufficient balance server-side before writing; a `CheckConstraint(balance >= 0)` is the DB-level
  backstop. No API endpoint or serializer can write `balance` — money only moves via verified
  events.
- **Wallet creation**: auto-created with the user (Prompt 02 signal now also creates `Wallet`).
- **API**
  - `GET /api/wallet/balance/` — `{balance, total_earnings, total_withdrawn}` (`total_withdrawn` is
    `0` until Prompt 12).
  - `GET /api/wallet/transactions/` — paginated ledger history; filters `?type=`, `?from=`, `?to=`
    (ISO dates).
  - `GET /api/wallet/pending-earnings/` — `{pending_earnings}` — the net (post-6%-fee) value of the
    user's **sold-but-not-yet-completed** items, computed server-side
    (`WalletService.pending_earnings`): items on a `PAID` order whose `item_status` is not
    `COMPLETED`/`CANCELLED`. Purely read-only; feeds the Earnings screen's "in transit" figure.

## Seller dashboard & listings (Prompt 11)

- **Seller hub**: the Profile tab's "Selling" link opens `MyListings` — the dashboard tying the
  seller flows together (`MyListings` → `AddProduct`/`EditProduct` via listing quick actions,
  `Selling`/`SellerOrders` via "Incoming orders", and `Earnings`).
- **Listings screen**: lists the user's products across *all* statuses by filtering the public
  product API with `?seller=<me>` (owner's view already includes drafts/inactive rows). Quick
  actions: view as buyer, edit, and deactivate/reactivate.
- **Deactivate/reactivate**: the write serializer now accepts `status = INACTIVE` in addition to
  `DRAFT`/`ACTIVE` (for pause/unpause). `SOLD` remains read-only — only the order system sets it.
  The existing `DELETE /api/products/{id}/` is still the soft delete.
- **Create/edit forms**: a single shared `ProductForm` (name, price, condition chips, quantity,
  location, description, category chips) with a multi-image picker
  (`expo-image-picker`, `allowsMultipleSelection`). Create posts `products/` then appends images via
  `POST /api/products/{id}/images/`; edit prefills from `fetchProduct`, supports deleting existing
  images (`DELETE /api/products/{id}/images/{image_id}/`) and appending new ones. Uploaded
  filenames are forced to `.jpg` because the backend extension validator rejects iOS HEIC picks
  (Pillow still content-verifies the bytes).
- **Earnings screen**: shows the wallet balance (in hand), **pending earnings** (in transit — not yet
  credited, separate from the balance so the two can't be conflated), lifetime earnings/withdrawn,
  and the ledger feed (shares the extracted `TransactionRow` component with the wallet screen).
- **Seller inbox refinements**: `GET /api/orders/selling/?item_status=` filters to orders containing
  at least one of the user's items in the given fulfillment state (all/`pending`/`confirmed`/
  `shipped`/`delivered`/`completed` chips). Each row now also renders the seller's item-level quick
  actions (`confirm`/`ship`/`deliver`) inline without opening the order first.
- **No withdrawals yet**: payout/withdrawal flows remain a Prompt 12 concern.

## Accounts & authentication (Prompt 02)

- **User model**: `accounts.User` (subclasses `AbstractUser`), `AUTH_USER_MODEL = "accounts.User"`,
  active from the first migration (fresh DB, no swap needed).
- **Identifier strategy**: `email` is the sole unique login identifier (`USERNAME_FIELD`),
  normalized to lowercase. `phone_number` lives on `Profile` (optional, unique when set).
  `username` is kept for Django admin/legacy compat only and is auto-derived from the email.
- **No roles**: registration accepts no buyer/seller role; every user has full buy+sell capability.
- **Profile** (`accounts.Profile`, OneToOne to `User`): full_name, profile_picture, address,
  account_status (ACTIVE/SUSPENDED), phone_number. Auto-created via `post_save` signal, as is the
  `Wallet` (Prompt 10).
- **JWT** (`rest_framework_simplejwt`): access/refresh lifetimes from env vars,
  `ROTATE_REFRESH_TOKENS=True`, `BLACKLIST_AFTER_ROTATION=True`, logout blacklists the refresh token.
- **Suspended accounts** are rejected at login with a clear error.
- **Password hashing**: Django default hasher (never plaintext). Password strength enforced with
  Django's built-in validators.

### Auth API

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/api/auth/register/` | None | Register (email, password, confirmation, full_name, phone?) → tokens |
| POST | `/api/auth/login/` | None | Login → access + refresh |
| POST | `/api/auth/refresh/` | None | Rotate refresh token (returns new refresh + access) |
| POST | `/api/auth/logout/` | Bearer | Blacklist the refresh token |
| GET | `/api/users/me/` | Bearer | Own user + profile |
| PATCH | `/api/users/me/` | Bearer | Update own profile fields |

### Backend commands

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in real values (never commit .env)
python manage.py migrate
python manage.py runserver    # serves against PostgreSQL
pytest                        # full suite (109 tests as of Prompt 08)
ruff check .                  # lint
ruff format .                 # format
```

## Chat & messaging (Prompt 13)

- **Delivery mechanism (chosen)**: **client polling**, not WebSockets. The app polls
  `GET /api/chats/{id}/messages/` every 5s while the conversation is focused, and refreshes the
  conversation list on tab focus. Rationale: zero extra dependencies or infra (a Channels deployment
  would need an ASGI server + a channels layer/Redis), it works with the existing JWT auth and
  Django dev server, and it is well within the real-time needs of a marketplace (slow message rate).
  Documented here so the alternative can be adopted later without redesigning the data model.
- **Models**
  - **Conversation**: `participants` (`ManyToManyField` User), optional `product` (FK catalog
    `SET_NULL`, for listing context), `created_at` / `updated_at`. Ordered by most-recently-active.
  - **Message**: `conversation` (FK CASCADE), `sender` (FK User), `body` (Text), `is_read`, `created_at`.
    Indexed on `(conversation, created_at, id)` for pagination.
- **Get-or-create rule**: a conversation between the same two users **about the same product** is
  reused rather than duplicated (`chat.services.get_or_create_conversation`). A direct thread
  (`other_user_id`, no product) is distinct from a product-scoped thread. Self-chat and missing
  counterparts are rejected.
- **Security**: object-level check on every conversation/message endpoint — a non-participant gets
  404 (they cannot read, post, or mark-as-read). Message body is capped at 4000 chars and blank
  messages are rejected (`chat.services.create_message`).
- **Unread state**: `Message.is_read` is set server-side on the recipient's `read` action;
  `ConversationSerializer.unread_count` counts inbound unread messages per requesting user.
- **API**

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/chats/` | Bearer | List own conversations (counterpart, last message, unread count) |
| POST | `/api/chats/` | Bearer | Get-or-create (`product_id` or `other_user_id`) |
| GET | `/api/chats/{id}/messages/` | Bearer | Paginated history, newest-first (`page`, `page_size`) |
| POST | `/api/chats/{id}/messages/` | Bearer | Send a message |
| POST | `/api/chats/{id}/read/` | Bearer | Mark inbound messages read |

### Mobile structure (Prompt 13 — chat)

| Path | Purpose |
| --- | --- |
| `src/api/chat.ts` | Typed chat endpoints + `pollNewMessages` helper for the poll loop |
| `src/screens/chat/ConversationListScreen.tsx` | Chat tab: conversation list (avatar, last-message preview, unread badge), pull-to-refresh, refresh on focus |
| `src/screens/chat/ConversationScreen.tsx` | Message bubbles, composer, auto-follow latest, load-older on scroll, 5s poll + mark-as-read while focused |
| `src/navigation/` | `Conversation` root route (opened from Chat tab and "Chat with Seller"), Chat tab points at the list screen |

The product-detail "Chat with Seller" button calls `POST /api/chats/` with `product_id` (get-or-create)
then navigates to the `Conversation` screen. Contact details remain hidden until an actual chat — this
satisfies the contact-reveal policy that deferred phone/email display to this prompt.

## Notifications (Prompt 14)

**Delivery model**: an in-app notification list is the delivery mechanism for this prompt.
Push (Expo) delivery is **explicitly deferred** — a future enhancement would add a push-token model
and send via Expo's push API without changing the `notify` signature. There are no push-token
endpoints today.

**Model**: `notifications.Notification` uses a generic relation (`content_type` + `object_id` +
`GenericForeignKey`) so it never imports other apps at module top (no import cycles), while the
serializer exposes `related_type`/`related_id` for deep-linking. A `Type` TextChoices enumerates
`order_update` / `payment_result` / `new_message` / `withdrawal_update` / `system`. A DB index on
`(user, is_read, -created_at)` backs the unread-count and list queries.

**Creation**: notifications are written **inside service methods, never in views**, via the single
`notifications.services.NotificationService.notify(...)` factory (best-effort, never raises):
- `orders.services` — `transition_order`/`transition_item` notify the *other* party: seller-initiated
  fulfillment (confirm/ship/deliver) → buyer; buyer completing receipt → seller; cancel / refund /
  mark-paid / fail-payment → buyer (and the sellers on a multi-seller refund).
- `payments.services.payment_service` — success/failure route through order transitions, so the
  `mark_paid`/`fail_payment` notifications above already surface as `payment_result`; no duplicate hook.
- `withdrawals.services.WithdrawalService.transition` — notifies the requester on every status change.
- `chat.services.create_message` — notifies the **recipient** (never the sender) on every inbound
  message. The "recipient not actively viewing" case is handled by in-chat read-marking plus the
  notification list's unread badge, rather than by suppressing creation.

**API**:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/notifications/` | Bearer | List own notifications, newest first |
| POST | `/api/notifications/{id}/read/` | Bearer | Mark one as read (own only) |
| POST | `/api/notifications/read-all/` | Bearer | Mark all own as read |
| GET | `/api/notifications/unread-count/` | Bearer | Unread count for the badge |

Every endpoint is scoped to `request.user`; a user can never see or mutate another user's notification.

### Mobile structure (Prompt 14 — notifications)
| File | Purpose |
|---|---|
| `src/api/notifications.ts` | Typed wrappers: list, read, read-all, unread-count |
| `src/hooks/useAppNotifications.ts` | List state (loading/refresh/reload), mirrors `useOrdersList` |
| `src/hooks/useUnreadNotificationCount.ts` | Focus-aware unread count for the entry badge |
| `src/screens/notifications/NotificationsScreen.tsx` | Notification list; tap deep-links by `related_type` (order → OrderDetails, conversation → Conversation, withdrawal → Wallet), optimistic read on tap, "mark all read" header |
| `src/screens/profile/ProfileScreen.tsx` | "Notifications" entry with unread badge |

## Reviews & ratings (Prompt 15)

**Completed-purchase restriction**: a review is tied to a *specific* `OrderItem` via a `UniqueConstraint`,
so the buyer can review a product only after that exact line reaches `item_status == COMPLETED` — one
review per purchased line (blocks spam and double-reviews). The create serializer checks server-side that
`request.user` is the `order_item`'s buyer **and** the item is `COMPLETED`, regardless of what the client
claims; the rating is validated to `1–5` plus a DB `CheckConstraint`. A `buyer` FK and a denormalized
`product` FK (snapshotted from the order item on create) make listing/aggregation cheap.

**Aggregation is server-computed** (never client-side):
- `catalog` `ProductViewSet` annotates `avg_rating` / `rating_count` per product; `ProductDetailSerializer`
  and the list serializer expose them (used by the product-details rating).
- `SellerSummarySerializer` computes a seller's `average_rating` / `rating_count` directly over reviews of
  their products (single aggregate query), surfacing real ratings in the product-detail seller mini-profile.

**API**:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/reviews/` | Bearer | Create a review `{order_item_id, rating, comment}` (restricted to COMPLETED purchase) |
| GET | `/api/reviews/product/{product_id}/` | Public | Paginated reviews for a product |
| GET | `/api/reviews/seller/{user_id}/` | Public | Seller public profile: summary + `average_rating`/`rating_count` + paginated reviews |

### Mobile structure (Prompt 15 — reviews)
| File | Purpose |
|---|---|
| `src/api/reviews.ts` | Typed wrappers: create, product reviews, seller profile |
| `src/components/StarRatingInput.tsx` | Tappable 1–5 star input for review creation |
| `src/components/ReviewItem.tsx` | Single review row (avatar, author, stars, comment), reused on product + seller views |
| `src/screens/reviews/ReviewScreen.tsx` | Star input + optional comment; `Review` root route |
| `src/screens/orders/OrderDetailsScreen.tsx` | "Write a review" button on COMPLETED items (buyer view) |
| `src/screens/marketplace/ProductDetailsScreen.tsx` | Real rating in seller mini-profile + reviews list section |

## Admin dashboard & moderation (Prompt 16)

The staff surface is **API-only** (`adminpanel` app mounts at `/api/admin/`) and is consumed by an
**in-app Admin tab** gated on `is_staff` — deliberately chosen over a separate web dashboard. This
keeps the product mobile-first with one codebase/re-auth path for a final-year project; every call
reuses the existing JWT client and the backend enforces `IsAdminUser` (staff or superuser) on all
endpoints.

**Design**: `adminpanel` defines **no new models** — it aggregates and mutates existing ones.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/admin/dashboard/` | GET | Aggregated stats + recent activity feed |
| `/api/admin/users/` | GET | Paginated user list, searchable (email/username/full name) |
| `/api/admin/users/{id}/` | GET | User detail + product/order/sold counts + wallet balance |
| `/api/admin/users/{id}/suspend/` | POST | Set `Profile.account_status = SUSPENDED` |
| `/api/admin/users/{id}/activate/` | POST | Restore `Profile.account_status = ACTIVE` |
| `/api/admin/products/` | GET | All products incl. inactive, searchable (name/seller/category) |
| `/api/admin/products/{id}/remove/` | POST | Deactivate to `INACTIVE` with a **required `reason`** |
| `/api/admin/categories/` | POST | Create category (slug auto-generated from name) |
| `/api/admin/categories/{id}/` | PATCH | Rename / move / deactivate a category |

Key behaviours:

- **Suspension ↔ login**: `LoginSerializer` already rejects non-`ACTIVE` accounts, so suspend/activate
  just flips `Profile.account_status`; a suspended user immediately loses login (verified by test).
  Admins/superusers cannot be suspended (400).
- **Dashboard efficiency**: all stats are single `aggregate()`/`annotate()` calls (no N+1). Fees are
  summed over `PLATFORM_FEE` ledger rows (stored negative → reported as `abs`). "Transaction value" is
  the sum of `Payment` rows with `status = SUCCESSFUL`.
- **Product removal is soft**: sets `status = INACTIVE` (hidden from public listings), never deletes,
  and the `reason` is recorded for consumption by the Prompt 17 audit log (no competing log built here).
- **Staff-gating is tested** on every endpoint (403 for members, 401 anonymous), plus suspend/login
  toggle, moderation deactivation, and category create with auto-slug.
- All existing `django.contrib.admin` registrations were reviewed and already adequate (list_display /
  list_filter / search_fields across accounts, catalog, orders, payments, wallet, withdrawals, chat,
  notifications, reviews) — no changes required.

### Mobile structure (Prompt 16 — admin)

| File | Purpose |
|---|---|
| `src/api/admin.ts` | Typed wrappers for all `/api/admin/` endpoints |
| `src/api/types.ts` | `AdminUser`, `AdminUserDetail`, `AdminProduct`, `AdminDashboard`, `AdminActivity` + `User.is_staff` |
| `src/screens/admin/AdminScreen.tsx` | Dashboard tab (stat grid + recent activity + moderation links) |
| `src/screens/admin/AdminUsersScreen.tsx` | Searchable user list → UserDetail |
| `src/screens/admin/AdminUserDetailScreen.tsx` | Activity summary + suspend/reactivate (disabled for staff) |
| `src/screens/admin/AdminProductsScreen.tsx` | Moderation list + confirm-removal modal with required reason |
| `src/navigation/AppStack.tsx` | `Admin` tab rendered only when `user.is_staff` |
| `src/navigation/RootNavigator.tsx` | `AdminUsers`, `AdminUserDetail`, `AdminProducts` stack routes |

`User.is_staff` was added to the `/api/users/me/` response (via `UserSerializer`) so the client can
gate the Admin tab; superusers are always staff and are covered by `is_staff`.

## Audit log & reporting (Prompt 17)

The `auditlog` app provides a **single, immutable audit trail** for every sensitive action across the
system, plus a staff-only reporting endpoint. It was chosen over bespoke per-feature logging so the
whole platform has one append-only record that cannot be rewritten (no create/update/delete routes,
and the Django admin is read-only).

**Design**: `AuditLogService.log()` is the only write path. It is best-effort (never raises, so a log
failure can never break a business action) and takes `actor`, `action`, `target`, `description`,
`before`/`after` snapshots, and an optional `request` (for IP capture). It **strips sensitive keys**
(`password`, `password_confirmation`, `token`, `refresh`, `access`, `mobile_money_number`,
`raw_provider_response`) recursively from snapshots before persisting. `actor=None` denotes a
system/anonymous-failed-login event.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/audit-logs/` | GET | Paginated, append-only list (filters: `actor`, `action`, `target_model`, `created_after`, `created_before`) |
| `/api/audit-logs/{id}/` | GET | Single entry |
| `/api/admin/reports/summary/?days=N` | GET | Daily `transaction_volume`, `fee_revenue`, `new_users` (staff-only) |

Key behaviours:

- **Append-only enforced** at the API layer (only GET routes exist → POST/PATCH/DELETE return
  405/404) and in `AuditLogAdmin` (add/change/delete permissions disabled).
- **Staff-gated**: members get 403, anonymous 401 on all audit/report routes.
- **Action vocabulary** (21 values): `auth.login`, `auth.login_failed`, `auth.logout`,
  `auth.register`, `auth.profile_update`, `product.create/update/delete`, `order.create`,
  `order.transition`, `payment.initiate/success/failure`, `withdrawal.request/transition`,
  `admin.user_suspend/user_activate/product_remove/category_create/category_update`.
- **Retrofit sites**: accounts (register, login success/failure, logout, profile update),
  catalog (product create/update/soft-delete), orders (creation + every transition), payments
  (initiation, success, failure, webhook), withdrawals (request + transition incl. admin notes),
  adminpanel (user suspend/activate, product removal w/ reason, category create/update). Services
  accept a `request=None` param so views pass the request for IP capture.
- **Reports** use `TruncDate` aggregates: transaction volume = SUCCESSFUL payments/day, fee revenue =
  `abs` of `PLATFORM_FEE` ledger rows/day, new users = daily registration counts.
- **Test coverage** (28 tests): staff-gating on all routes, filter correctness, no destructive
  routes, a row produced per retrofit action, and a no-sensitive-data scan over persisted snapshots.

### Mobile structure (Prompt 17 — audit & reports)

| File | Purpose |
|---|---|
| `src/api/types.ts` | `AuditLogEntry`, `AdminReportSummary` types |
| `src/api/admin.ts` | `fetchAuditLogs`, `fetchAuditLogEntry`, `fetchAdminReports` wrappers |
| `src/screens/admin/AuditLogScreen.tsx` | Filterable, paginated audit log (action, actor, IP, target) |
| `src/screens/admin/ReportsScreen.tsx` | Daily transaction volume / fee revenue / new-users tables |
| `src/screens/admin/AdminScreen.tsx` | "Security & insights" card linking to Audit log + Reports |
| `src/navigation/RootNavigator.tsx` | `AuditLog` and `Reports` stack routes |

## Full-stack integration & polish (Prompt 18)

This stage added **no new business features** — it hardened and completed the integration of every
screen from Prompts 05–17 and closed two genuine gaps found during the audit: the **cart flow had no
mobile client** (backend from Prompt 07 was fully built but never consumed) and **withdrawal requests
had no mobile UI** (backend Prompt 12 was also built but unreachable from the app).

### Backend changes made in this stage

Only two backend changes were needed, both discovered during the integration audit (no new endpoints
or models):

| Change | File | Why |
|---|---|---|
| Added `product_name`, `product_image`, `condition` to `CartItemSerializer` | `cart/serializers.py` | The cart item response previously exposed only `product_id`, so the client could not render product names/images without an extra lookup. Added as read-only fields sourced from the related product. |
| Added `cart/test_api.py::AnonymousCartTests::test_add_item_to_anonymous_cart` assertions | `cart/test_api.py` | Regression coverage for the new serializer fields. |

Both changes are additive and read-only; no migration was required (`manage.py makemigrations --check`
reports no changes, `manage.py check` clean).

### Frontend changes made in this stage

**Cart & checkout (new — the missing buyer-journey leg):**

| File | Purpose |
|---|---|
| `src/api/cart.ts` | `fetchCart`, `addToCart`, `updateCartItemQuantity`, `removeCartItem`, `checkoutCart` (POST `/orders/`) |
| `src/api/types.ts` | `Cart`, `CartItem`, `CartItemPayload`, `CheckoutPayload` types |
| `src/screens/cart/CartScreen.tsx` | Full cart list with quantity steppers, remove, pull-to-refresh, loading/empty/error states, subtotal footer |
| `src/screens/cart/CheckoutScreen.tsx` | Shipping details form → `checkoutCart` → `navigation.replace('Payment')` |
| `src/screens/marketplace/ProductDetailsScreen.tsx` | "Add to Cart" now calls `addToCart` (was a placeholder toast), with submitting state + success toast |
| `src/navigation/AppStack.tsx` | Cart icon in the Home header |
| `src/navigation/RootNavigator.tsx` + `types.ts` | `Cart` and `Checkout` stack routes |

**Withdrawal (new — the missing seller-journey leg):**

| File | Purpose |
|---|---|
| `src/api/wallet.ts` | `requestWithdrawal` (POST `/withdrawals/`), `fetchWithdrawals` |
| `src/api/types.ts` | `WithdrawalRequest`, `WithdrawalPayload`, provider/status types |
| `src/screens/wallet/WithdrawalScreen.tsx` | Provider chips, amount + mobile-money number form, balance-aware validation, submitting state, success toast |
| `src/screens/wallet/BalanceScreen.tsx` | "Withdraw" button on the balance card |
| `src/navigation/RootNavigator.tsx` + `types.ts` | `Withdraw` route |

**Design-system consolidation** (from the component audit):

- Added `src/components/ErrorBoundary.tsx` (global render-crash guard, wired in `App.tsx`).
- Added shared `src/components/Badge.tsx` and `src/components/Chip.tsx`.
- Refactored admin screens (`AdminUsersScreen`, `AdminProductsScreen`, `AuditLogScreen`) to use
  `AppTextInput` and `Badge`, removing duplicated ad-hoc search/badge styles.
- `ToastContext` now uses theme tokens instead of inline hex; `Skeleton` uses `colors.border`.
- Added pull-to-refresh to the conversation screen (already present on Home, Orders, Notifications,
  Chat list, Wallet, Earnings, MyListings).

### Journey verification

Both full journeys are exercised **end-to-end through the real HTTP API** (ClickPesa mocked at the
service boundary) by `payments/test_journeys.py`. They are the automated counterpart to the manual
checklist below.

| Step | Buyer journey | Seller journey |
|---|---|---|
| 1 | register | register |
| 2 | browse marketplace | list product (create → activate) |
| 3 | add to cart | receive order (cart + checkout + paid webhook) |
| 4 | checkout (order from cart, cart drained) | see incoming order (`/orders/selling/`) |
| 5 | pay (initiate + successful ClickPesa webhook → PAID) | fulfil (confirm → ship → deliver → buyer completes) |
| 6 | track order (buyer detail) | get paid (net of 6% fee credited to wallet) |
| 7 | receive (buyer confirms complete) | see earnings + withdraw (POST `/withdrawals/`) |
| 8 | review completed item | — |

Each step asserts the HTTP status and resulting domain state, so a regression in any leg fails loudly.

## Frontend (Expo + React Native)

- **App**: Expo (SDK 57), TypeScript strict
- **Navigation**: React Navigation — `native-stack` for the auth gate + marketplace detail
  screens, `bottom-tabs` for the authenticated area (Home / Search / Chat / Profile). Splash
  renders while the stored session is validated, then the root stack swaps between `AuthStack`
  and the authenticated tree (`Tabs` + ProductDetails / Category / Filters stack screens).
- **State management**: React Context + `useReducer` (no Redux). The only global state is the
  session (`AuthContext`); a separate `ToastContext` owns the global error/success toast.
- **HTTP**: Axios singleton in `src/api/client.ts`; base URL from `EXPO_PUBLIC_API_URL`.
  - Request interceptor attaches the JWT access token from secure storage.
  - Response interceptor: on 401 → rotate the refresh token once and retry the original request
    (deduplicated across concurrent 401s). Refresh failure clears tokens and routes back to Login.
    `/auth/login|register|refresh` are exempt (a 401 there is bad credentials, not an expired session).
- **Token storage**: `expo-secure-store` (keychain/keystore) — never AsyncStorage for tokens.
- **Error handling**: no scattered `Alert.alert`. Form errors render an `ErrorBanner`; transient
  errors surface via the shared `useToast` provider. `getErrorMessage()` normalizes DRF error bodies.
- **Env**: `EXPO_PUBLIC_*` vars only (inlined into the client bundle — never store secrets here)

### Mobile structure (Prompt 05)

| Path | Purpose |
| --- | --- |
| `src/api/types.ts` | Shared API types (AuthResponse, User, error envelope) |
| `src/api/tokenStorage.ts` | Secure token get/save/clear via expo-secure-store |
| `src/api/client.ts` | Axios client + 401 refresh-retry interceptors |
| `src/api/auth.ts` | Typed auth endpoints (register/login/logout/me) |
| `src/api/errors.ts` | DRF error → message extraction |
| `src/context/AuthContext.tsx` | Session state (loading/authenticated/unauthenticated) + signIn/signUp/signOut |
| `src/context/ToastContext.tsx` | Global toast surface |
| `src/components/` | Button, TextInput, Card, LoadingSpinner, ErrorBanner, PlaceholderScreen |
| `src/navigation/` | RootNavigator (auth gate), AuthStack (Login/Register/ForgotPassword), AppStack (tabs) |
| `src/screens/auth/` | Splash, Login, Register, ForgotPassword (placeholder — no backend endpoint yet) |

> **Auth gap note**: the backend has no password-reset endpoint (Prompt 02 shipped only
> register/login/refresh/logout/me), so ForgotPassword is an honest placeholder rather than a
> fake API call. It will be wired when a reset endpoint exists.

### Mobile structure (Prompt 06 — marketplace browsing)

| Path | Purpose |
| --- | --- |
| `src/api/catalog.ts` | Typed catalog endpoints: products (list/filter/search/paginate), detail, categories, favorites |
| `src/hooks/useProductFeed.ts` | Shared paginated feed (skeleton / refresh / infinite scroll), reloads on param change |
| `src/hooks/useCategories.ts` | Shared category list used by Home chips, Search filter labels and the Filters modal |
| `src/hooks/useDebouncedValue.ts` | Debounces the search query (400 ms) before it hits the feed |
| `src/components/ProductGrid.tsx` | 2-column FlatList shared by Home / Category / Search: skeleton, empty, error, pull-to-refresh, infinite scroll |
| `src/components/ProductCard.tsx` | Listing card (image, price, location, condition, favorite heart) |
| `src/components/CategoryChips.tsx` | Horizontal category pills (Home header) |
| `src/components/RatingStars.tsx` | Display component for a rating + count (Prompt 15 wires real values) |
| `src/components/ImageCarousel.tsx` | Paged product-image carousel with dot indicators (detail screen) |
| `src/screens/marketplace/` | HomeScreen, CategoryScreen, SearchScreen, FiltersScreen, ProductDetailsScreen |
| `src/navigation/RootNavigator.tsx` | Tabs + ProductDetails / Category / Filters stack screens on top of the tab navigator |

### Mobile structure (Prompt 08 — orders)

| Path | Purpose |
| --- | --- |
| `src/api/orders.ts` | Typed orders endpoints (buyer list/detail, `selling/`, cancel, item confirm/ship/deliver/complete) |
| `src/hooks/useOrdersList.ts` | Shared list state (loading / pull-to-refresh / retry) for the two order lists |
| `src/components/StatusBadge.tsx` | Colored status chip shared by order + item rows |
| `src/screens/orders/OrdersScreen.tsx` | Buyer's orders list (status badge, total, tap → details) |
| `src/screens/orders/SellerOrdersScreen.tsx` | Seller's incoming-orders list (buyer name shown) |
| `src/screens/orders/OrderDetailsScreen.tsx` | Order detail: totals, per-item status + seller, and action buttons driven by `available_actions` |
| `src/navigation/` | `Orders`, `Selling`, `OrderDetails` stack routes; Profile links into both lists |

Order actions render only from the backend `available_actions` list, so the UI never offers an
invalid transition. Action responses return the updated order and the detail screen refreshes in
place; failures surface via the global toast.

**Contact-reveal policy** — listings never show a seller's phone number or email (the API exposes
`Seller.email` but the UI deliberately omits it). Contact details are revealed only when Prompt 13
ships in-app chat; the detail screen shows name + avatar + a ratings placeholder instead. Order
fulfillment is the exception: the seller's order detail shows the buyer's name/phone so delivery
can be arranged.

**UI decisions**
- Prices render as plain grouped numbers (`formatPrice`) — the product model has no currency field,
  so the UI doesn't invent a symbol. Filter labels stay symbol-free too.
- Cart / Chat buttons on the detail screen are honest stubs: tapping shows an info toast naming the
  prompt that wires the feature (Prompt 07 / Prompt 13) rather than silently doing nothing.

### Mobile commands

```bash
cd mobile
npm install
cp .env.example .env   # set EXPO_PUBLIC_API_URL to your backend, e.g. http://<LAN-IP>:8000/api
npm start              # Expo dev server (Metro on :8081)
npm run lint           # expo lint (eslint-config-expo + prettier rules)
npm run format         # prettier --write .
npm run typecheck      # tsc --noEmit
npm test               # jest (jest-expo)
```

## Environment variables

| Variable | Where | Required | Notes |
| --- | --- | --- | --- |
| `DJANGO_SECRET_KEY` | backend | yes | Generate a long random value; no defaults in code |
| `DEBUG` | backend | yes | Defaults to `False`; only `True` via explicit local env |
| `POSTGRES_*` | backend | yes | DB name/user/password/host/port |
| `CORS_ALLOWED_ORIGINS` | backend | dev | Comma-separated origins allowed to call the API |
| `JWT_*` | backend | dev | Token lifetimes |
| `CLICKPESA_*` | backend | later | ClickPesa keys — placeholders only in `.env.example` |
| `EXPO_PUBLIC_API_URL` | mobile | dev | Backend base URL; visible to end users |

## Security rules

- `.env` files are git-ignored everywhere; only `.env.example` is committed
- `DEBUG` defaults to `False`; enable only explicitly in local dev
- No real secrets in git history or tracked files
- `EXPO_PUBLIC_*` values are embedded in the shipped app — never put secrets there

## Testing & tooling

| Layer | Tool | Current coverage |
| --- | --- | --- |
| Backend | pytest + pytest-django (chosen over Django's test runner for fixtures/plugins) | Smoke: project boots, settings load, Postgres connectivity |
| Backend lint | ruff (check + format) | Runs clean |
| Mobile | Jest + jest-expo (axios-mock-adapter) | Config sanity + Axios refresh-retry interceptor (mocked) |
| Mobile lint | ESLint (eslint-config-expo) + Prettier | Runs clean |
| Mobile types | TypeScript strict (`tsc --noEmit`) | Passes |

## Acceptance checklist

### Prompt 01

- [x] `backend/` runs `runserver` against PostgreSQL via env vars
- [x] `mobile/` runs `npx expo start` and serves the placeholder screen
- [x] No secrets in git history or tracked files
- [x] `docs/ARCHITECTURE.md` lists all planned Django apps
- [x] Linting configured and clean on existing code

### Prompt 02

- [x] Custom `accounts.User` active from the first migration (no swap needed later)
- [x] Registration accepts no Buyer/Seller role
- [x] JWT register/login/refresh/logout works end-to-end (23 tests pass)
- [x] Suspended users cannot authenticate (blocked at login)
- [x] Profile auto-created via `post_save`; Wallet TODO left for Prompt 10

### Prompt 03

- [x] Migrations apply cleanly on PostgreSQL (constraints + indexes verified)
- [x] Category, Product, ProductImage, Favorite visible and usable in Django admin
- [x] DB constraints reject negative price/quantity (CheckConstraint + `clean()`)
- [x] Image validation (extension/MIME/size/content) enforced at the model layer
- [x] 14 catalog model tests pass (full suite: 37)

### Prompt 04

- [x] Catalog API endpoints (`/api/products/`, `/api/categories/`, `/api/favorites/`, image upload/delete)
- [x] Pagination (PageNumberPagination, page size 20), filtering, search, owner-scoped visibility
- [x] Soft delete (status → INACTIVE); primary-image promotion on delete
- [x] 28 catalog API tests pass (full suite: 65)

### Prompt 05

- [x] Navigation skeleton: RootNavigator auth gate + AuthStack + AppStack (bottom tabs), per Part A.5
- [x] Login/Register/Splash work against the real Prompt 02 endpoints (register auto-starts the session)
- [x] Token refresh-on-401 (single-flight, retry-once) verified by mocked unit tests
- [x] No Buyer/Seller role selection anywhere in the UI (register takes no role)
- [x] Reusable component set (Button, TextInput, Card, LoadingSpinner, ErrorBanner) used by the auth screens
- [x] Tokens in expo-secure-store; logout clears them and blacklists the refresh token server-side

### Prompt 06

- [x] Home feed: 2-column product grid with skeleton, empty, error, pull-to-refresh and infinite scroll
- [x] Category chips on Home link to a filtered Category screen (header titled by category)
- [x] Search tab: debounced keyword search against the Prompt 04 API
- [x] Filters modal: category, condition, price range, location → applies to the Search results
  (badge-counted, individually clearable chips)
- [x] Product detail: image carousel, condition/price/name/location, description, seller card, favorite,
  and stub Cart / Chat actions (toast informs which prompt wires them)
- [x] Contact-reveal policy: no phone or email shown on listings (see above)
- [x] Lint + typecheck + prettier clean, tests still pass

### Manual test checklist (Prompt 05)

Run `cd backend && python manage.py runserver` and `cd mobile && npm start` (set
`EXPO_PUBLIC_API_URL` to the backend on your LAN if testing on a device):

1. **Register**: create an account → session starts automatically and lands on the Home placeholder.
2. **Login**: log in → lands on the Home placeholder (bottom tab bar visible).
3. **Invalid credentials**: wrong password → error banner on the form, stays on Login, no crash.
4. **Session restore**: log in, kill and reopen the app → Splash validates the stored token and lands
   back on Home without asking for credentials.
5. **Logout**: Profile tab → Log out → returns to Login, tokens removed from secure storage.
6. **Refresh on 401**: with the backend running, shorten `JWT_ACCESS_TOKEN_LIFETIME` to ~1 minute,
   wait past expiry, perform any authenticated request → app rotates the refresh token seamlessly.
7. **Register has no role choice**: the Register form exposes only name/email/phone/password fields.

### Manual test checklist (Prompt 06)

Seed a couple of products across categories (Django admin) before testing.

1. **Home grid**: recent listings load newest-first; pull-to-refresh works; scrolled to the end, "You're all caught up" appears.
2. **Offline first load**: kill the network, cold-start Home → skeleton, then an error state with Retry (no crash).
3. **Category flow**: tap a chip → Category screen shows only that category's products, header shows the category name; back returns to Home.
4. **Search**: typing filters results after ~400 ms of quiet; clearing the query restores the feed.
5. **Filters**: open Filters from Search → pick category + condition + price range + location → Apply → results narrow; chips show the active filters and clear individually / "Clear all".
6. **Product detail**: image carousel (dots track pages), condition badge, price, description, seller card (name + avatar + "New seller" placeholder, no contact info).
7. **Favorite heart**: tap the heart on a card or detail → it persists across screens (FavoritesContext); toast on backend failure.
8. **Stubs**: Add to Cart / Chat show an info toast naming the wiring prompt (07 / 13) — no crash, no silent no-op.

### Prompt 07 (cart + orders backend)

- [x] Cart endpoints: anonymous session carts + per-user carts, add/update/remove items, owner-scoped access
- [x] Orders endpoints: create order from cart (transactional snapshot + cart flush), list/detail scoped to the user
- [x] Anonymous cart merged into the user's cart when an order is placed by a logged-in user
- [x] Money stays `Decimal` end-to-end; totals formatted via `int_to_pretty`
- [x] Cart/Order models in Django admin; DB constraints (owner XOR session_key, unique cart product, quantity 1–100)
- [x] 16 cart/orders tests pass (full suite: 81)

### Prompt 08 (order management & lifecycle)

- [x] `Order.status` finalized (`pending_payment/paid/confirmed/shipped/delivered/completed/cancelled/payment_failed/refunded`),
      old `pending` data-migrated to `pending_payment`
- [x] Multi-seller model: `OrderItem.seller` + per-item `item_status`; envelope vs. fulfillment states documented
- [x] Single reusable state machine (`orders/state_machine.py`) + transition service (`orders/services.py`);
      no raw status writes from views, no generic PATCH
- [x] Strict per-transition role checks (buyer / item seller / admin / payment); 400 vs 403 vs 404 semantics
- [x] Order + item action endpoints (`cancel`, `mark-paid`, `refund`, `confirm`, `ship`, `deliver`, `complete`),
      `selling/` list & detail for sellers
- [x] Buyer `OrdersScreen`, `SellerOrdersScreen`, `OrderDetailsScreen` with status badges + action buttons
      driven by backend `available_actions`
- [x] Indexes on `Order.status`, `Order.buyer`, `OrderItem.seller`, `OrderItem.item_status`
- [x] 34 orders tests incl. every transition + negative cases (full suite: 109); mobile lint/typecheck/tests clean

### Prompt 19 (testing, security, financial consistency)

See `docs/SECURITY_AUDIT.md` for the full checklist walkthrough; this section
summarises the code changes and added tests.

**Security fixes (all in `config/settings.py`, `accounts/views.py`, `payments/views.py`):**

- [x] `AUTH_PASSWORD_VALIDATORS` enabled (was empty) — similarity / min length 8 /
      common / numeric validators. Also fixes the previously-failing
      `RegisterTests.test_register_weak_password_rejected`, which is no longer
      deselected.
- [x] DRF throttling configured: global `Anon`/`User` throttles plus tighter
      per-scope `ScopedRateThrottle`s on login (`auth_login`, default `10/min`)
      and payment initiation (`payment_initiate`, default `15/min`). All rates
      are env-tunable (`THROTTLE_*`). `backend/conftest.py` raises every limit
      for the test suite while production defaults stay strict.

**New tests:**

- [x] `accounts/tests.py::JwtSecurityTests` — expired access rejected, expired
      refresh cannot rotate, suspended user with a valid (pre-suspension) token
      blocked on a protected write, active user succeeds (proves the gate is
      account status, not the token).
- [x] `accounts/tests.py::LoginThrottleTests` — login returns `429` above its
      scope rate.
- [x] `payments/test_financial_consistency.py` (TransactionTestCase + real
      threads so row locks contend):
  - ledger reconciliation — 80 randomized sales/debits/withdrawals/refunds,
    balance == ledger sum and never negative after every step
  - duplicate payment callbacks — two concurrent webhooks process once, order
    paid once
  - concurrent withdrawals — racing requests against one wallet cannot over-draw

**Files:** `docs/SECURITY_AUDIT.md`, `config/settings.py`, `accounts/views.py`,
`payments/views.py`, `accounts/tests.py`, `payments/test_financial_consistency.py`,
`backend/conftest.py`.
