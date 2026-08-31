# Security Audit

**Prompt 19.** A dedicated hardening pass against the security checklist from
Part 14. Each item records the finding, the fix (if any), and the test or
evidence backing it. Property tests live in `backend/payments/` and
`backend/accounts/tests.py`; per-module evidence is cited by file/line.

The audit was conducted against the checklist in the project spec. Statuses:

- **PASS** — implemented and covered by a test or directly verified in code.
- **FIXED** — a problem was found and remediated during this audit.
- **N/A** — not applicable to this codebase / no such surface exists.

---

## 1. JWT configuration

**Status: PASS**

- Access lifetime 1 day, refresh 7 days — both environment-tunable
  (`JWT_ACCESS_TOKEN_LIFETIME_DAYS`, `JWT_REFRESH_TOKEN_LIFETIME_DAYS`).
- `ROTATE_REFRESH_TOKENS = True` and `BLACKLIST_AFTER_ROTATION = True` — every
  refresh issues a new refresh/access pair and blacklists the old refresh, so a
  rotated-out refresh token cannot be replayed (supported by
  `TokenTests.test_refresh_rotates_token`).
- `auditlog` is in `INSTALLED_APPS`, so the simplejwt blacklist tables exist.
- New coverage added here: expired access and expired refresh tokens are
  rejected (`accounts.tests.JwtSecurityTests`).

## 2. Password hashing & validation

**Status: FIXED**

- **Finding:** `AUTH_PASSWORD_VALIDATORS` was empty (all four validators were
  commented out). The register serializer *called* `validate_password`
  (`accounts/serializers.py:50`) but with no active validators it accepted
  weak passwords — the only code path was third-party, so this was a real gap.
- **Fix:** enabled `UserAttributeSimilarity`, `MinimumLength` (8),
  `CommonPassword` and `NumericPassword` validators in `config/settings.py`.
  This also makes the pre-existing `RegisterTests.test_register_weak_password_rejected`
  pass; that test is no longer deselected.
- Hashing stays on Django's default PBKDF2 (not overridden) — **PASS**.
- New coverage: `RegisterTests.test_register_weak_password_rejected` (numeric
  password rejected) now green.

## 3. Endpoint authorization / `permission_classes`

**Status: PASS**

- Global default is `IsAuthenticated`; `AllowAny` is set only on the five public
  surfaces that must be open: register, login, refresh (simplejwt), the ClickPesa
  webhook (authenticated by checksum, `authentication_classes = []`), and public
  catalog reads.
- Writes across the app are additionally gated: catalog by `IsActiveUser` +
  `IsOwnerOrReadOnly`, payments by `IsOrderBuyer`, withdrawals by staff checks,
  admin panel by its own admin permission class.

## 4. Object-level access control

**Status: PASS**

- `IsOwnerOrReadOnly` limits writes to the object owner (`catalog/permissions.py`).
- Payment endpoints gate on `IsOrderBuyer`; wallet/withdrawals views filter
  querysets to `request.user`; admin panel is staff-only; audit log is
  read-only for staff. Covered by module tests (e.g.
  `payments.test_payments.PaymentInitiateTests.test_initiate_scoped_to_buyer`).

## 5. Suspended / deactivated user enforcement

**Status: PASS (coverage added)**

- Login rejects any non-`ACTIVE` account (`accounts/serializers.py:92`).
- Writes on protected endpoints reject suspended users via `catalog.permissions.IsActiveUser`.
- **New coverage:** `JwtSecurityTests.test_suspended_user_with_valid_token_is_blocked`
  proves a token issued *before* suspension is still rejected on a protected
  write, even though the JWT itself remains cryptographically valid. The
  complementary `test_active_user_token_completes_same_write` proves the gate is
  the account status, not the token.

## 6. Secrets handling

**Status: PASS**

- `DJANGO_SECRET_KEY` (no default), ClickPesa client ID / API key / webhook
  secret and DB credentials are read **only** from `.env` / environment
  variables; `.env` is git-ignored.
- `SECRET_KEY = env("DJANGO_SECRET_KEY")` has no fallback, so a deploy without
  it fails loudly.
- Payment credentials are server-side only and never serialized to clients.

## 7. CORS / host policy

**Status: PASS**

- `CORS_ALLOWED_ORIGINS` default empty; `CORS_ALLOW_ALL_ORIGINS` defaults to
  `False` — the API does not allow arbitrary origins by default.
- `ALLOWED_HOSTS` is environment-configured; `DEBUG` defaults to `False`.
- Deployments must set an explicit `CORS_ALLOWED_ORIGINS` allow-list for the
  mobile client origin.

## 8. Brute-force / rate limiting

**Status: FIXED (new capability + coverage)**

- **Finding:** DRF throttling was not configured — login and the payment
  initiation endpoint had no rate limit.
- **Fix:** added default `AnonRateThrottle` / `UserRateThrottle` everywhere and
  tighter per-scope throttles on sensitive endpoints:
  - `auth_login` -> default `10/min` (login brute force), via
    `ScopedRateThrottle` on `accounts.views.LoginView`.
  - `payment_initiate` -> default `15/min`, via `ScopedRateThrottle` on
    `payments.views.PaymentInitiateView`.
  - All rates are environment-tunable (`THROTTLE_*`).
- The test suite raises all limits via `backend/conftest.py` so the long run
  never trips them, while production defaults stay strict.
- **New coverage:** `LoginThrottleTests.test_login_rate_limited_after_burst`
  re-lowers the scope to `2/min` and asserts the third attempt returns `429`.

## 9. Atomicity & transaction boundaries

**Status: PASS**

- Wallet mutations (`WalletService`) run inside `transaction.atomic()` and take
  `select_for_update` on the wallet row, serializing concurrent writers.
- Withdrawal request + hard-debit happen in one transaction; reversal
  (FAILED/REJECTED -> REFUND) is written in the same transaction as the status
  change, so a reversal can never leave the balance inconsistent
  (`withdrawals/services.py`).
- Payment webhook processing is atomic and re-checks the payment is still
  `PENDING` inside the lock (duplicate callbacks are no-ops).

## 10. Financial idempotency

**Status: PASS**

- Sale crediting is idempotent in three layers: a service-level existence check,
  a DB `(order_item, type)` unique constraint, and row locking
  (covered by `wallet/tests.py` and the concurrency test).
- Payment webhooks are idempotent: a payment already in a final state is a no-op
  (`payments/test_payments.py`, plus new concurrency coverage below).
- Withdrawal transitions are serialized on the request row; a terminal request
  cannot be moved again.

## 11. Ledger / wallet reconciliation invariant

**Status: PASS (new property test)**

- **New coverage:** `payments/test_financial_consistency.py::LedgerReconciliationTests`
  runs a randomized 80-step mix of sales, debits, withdrawals and refunds against
  one wallet and asserts after every step that (a) `Wallet.balance` equals
  `reconcile_balance`, (b) the balance never goes negative, and (c) an
  independent running total matches both.

## 12. Sensitive data exposure in serializers

**Status: PASS**

- `UserSerializer` never outputs `password`; register confirms passwords are
  write-only (`accounts/serializers.py`); `MeTests.test_me_returns_own_profile`
  asserts `password` is absent.

## 13. Admin / privileged actions

**Status: PASS**

- Withdrawal transitions and admin-panel actions require `is_staff`; enforced in
  `withdrawals/tests.py` (`test_non_staff_cannot_transition`,
  `test_admin_actions_require_staff_and_wire_transitions`) and `adminpanel/tests.py`.

## 14. Audit logging

**Status: PASS**

- A dedicated `auditlog` app records register/login/logout/profile changes,
  order/payment/withdrawal events and admin actions. The audit log itself is
  read-only in the API (no client can create or mutate audit entries).

---

## Concurrency / stress coverage (mandated)

All in `backend/payments/test_financial_consistency.py` (run with real threads on
`TransactionTestCase`, so row locks actually contend):

| Test | Proves |
|------|--------|
| `LedgerReconciliationTests.test_randomized_operations_keep_ledger_and_balance_reconciled` | randomized financial ops never drift the ledger/wallet or go negative |
| `DuplicateCallbackConcurrencyTests.test_concurrent_duplicate_callbacks_process_once` | two concurrent webhooks process the payment exactly once; order paid once |
| `ConcurrentWithdrawalTests.test_concurrent_withdrawals_never_overdraw` | racing withdrawals against one wallet can never over-draw it |

---

## New JWT / auth coverage (mandated)

All in `backend/accounts/tests.py::JwtSecurityTests` and `LoginThrottleTests`:

- expired access token rejected; expired refresh token cannot rotate
- suspended user with a valid (pre-suspension) token blocked on a protected write
- active user with the same token succeeds (proves the gate is status, not token)
- login endpoint returns `429` after a burst above the scope rate

---

*Generated during Prompt 19. Every FIXED item is addressed in `config/settings.py` /
`accounts/views.py` / `payments/views.py` and covered by the tests referenced above.*