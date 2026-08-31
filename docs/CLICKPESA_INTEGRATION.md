# ClickPesa Integration (Prompt 09)

Findings recorded **before** writing any ClickPesa-specific code, from the current
official docs at https://docs.clickpesa.com (fetched August 2026). Implement against
this document; if ClickPesa changes the API, update this file first.

## Base URL & environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `CLICKPESA_BASE_URL` | `https://api.clickpesa.com/third-parties` | API root for all calls below |
| `CLICKPESA_CLIENT_ID` | *(none)* | Application Client ID (`client-id` header) |
| `CLICKPESA_API_KEY` | *(none)* | Application API key (`api-key` header) — shown once at creation |
| `CLICKPESA_WEBHOOK_SECRET` | *(none)* | Checksum key used to sign/verify webhook payloads |
| `CLICKPESA_CURRENCY` | `TZS` | Currency sent to ClickPesa (USSD-PUSH only accepts `TZS`) |
| `CLICKPESA_WEBHOOK_BASE_URL` | *(none)* | Public HTTPS base the gateway reaches. The path `/api/payments/webhook/clickpesa/` is appended and sent as `webhookUrl` per payment. If unset, the dashboard webhook URL is used. |

Credentials are read from the environment only and are **never** exposed to the
mobile app or included in any API response. The webhook URL
`POST /api/payments/webhook/clickpesa/` is configured per-application in the
ClickPesa dashboard (Settings → Developers → application → Webhooks) **and/or**
sent per-payment as `webhookUrl` on initiation (when `CLICKPESA_WEBHOOK_BASE_URL`
is set), which lets multiple products use distinct webhook endpoints.

## Authentication — Generate Authorization Token

`POST {CLICKPESA_BASE_URL}/generate-token`

- Headers: `client-id: <CLIENT_ID>`, `api-key: <API_KEY>`
- Response: `{ "success": true, "token": "Bearer <jwt>" }`
- The JWT is valid for **1 hour**; the service caches it and refreshes on expiry/401.

## Initiate USSD-PUSH request (collection method used by ReuseHub)

`POST {CLICKPESA_BASE_URL}/payments/initiate-ussd-push-request`

- Auth: `Authorization: Bearer <token>` (the token already includes the `Bearer` prefix)
- Body:

```json
{
  "amount": "150000",
  "orderReference": "RH-1-2",
  "phoneNumber": "255712345678",
  "currency": "TZS",
  "webhookUrl": "https://api.reusehub.xyz/api/payments/webhook/clickpesa/",
  "checksum": "<optional if checksum enabled>"
}
```

- `amount` is a **string**. `phoneNumber` starts with country code, no `+`.
  `orderReference` must be alphanumeric and **unique per attempt** (a reused
  reference returns `409 Conflict: Order reference ... already used`).
  `webhookUrl` is optional and overrides the dashboard webhook per request.
- Success response:

```json
{
  "id": "ORD123456LCP7890",
  "status": "PROCESSING",
  "channel": "TIGO-PESA",
  "orderReference": "RH-1-2",
  "collectedAmount": "150000",
  "collectedCurrency": "TZS",
  "createdAt": "2026-08-09T10:00:00.000Z",
  "clientId": "ID1234XHYAJK"
}
```

- `status` is one of `PROCESSING | SUCCESS | FAILED | SETTLED`. The buyer completes
  payment via the USSD push on their phone (the "USSD prompt reference" the client
  displays).

Card payment (`initiate-card-payment`, USD + `cardPaymentLink`) exists but is **not**
used: our order model has no currency field and this is a TZS marketplace, so USSD-PUSH
is the documented collection method.

## Query payment status (manual verify fallback)

`GET {CLICKPESA_BASE_URL}/payments/{orderReference}`

- Auth: `Authorization: Bearer <token>`
- Response: array of payment objects, each with `status` in
  `SUCCESS | SETTLED | PROCESSING | PENDING | FAILED`, plus `paymentReference`,
  `collectedAmount`, `collectedCurrency`, `message`, `createdAt`, `updatedAt`.
- Used by `POST /api/payments/{order_id}/verify/` when webhooks are delayed/unavailable.

## Webhooks (payment callbacks)

ClickPesa POSTs to the configured webhook URL. Events relevant to ReuseHub:

- **`PAYMENT RECEIVED`** — `data.status == "SUCCESS"` (money arrived).
- **`PAYMENT FAILED`** — attempt failed; `data.message` holds the failure reason.
- **`PAYMENT CANCELLED`** — attempt cancelled by the user / timed out; treated as a failure.

Event names are normalised across ClickPesa's spellings (`PAYMENT RECEIVED`,
`PAYMENT_RECEIVED`, `payment.received`, ...). Non-payment events (`PAYOUT ...`,
`DEPOSIT ...`) are acknowledged and ignored.

Sample `PAYMENT RECEIVED` payload:

```json
{
  "event": "PAYMENT RECEIVED",
  "data": {
    "id": "ORD123456LCP7890",
    "status": "SUCCESS",
    "paymentReference": "abc123def456ghi789",
    "orderReference": "RH-1-2",
    "collectedAmount": "10000",
    "collectedCurrency": "TZS",
    "message": "success",
    "channel": "TIGO-PESA",
    "updatedAt": "2026-08-09T10:02:56.153Z",
    "createdAt": "2026-08-09T10:00:16.949Z",
    "customer": { "customerName": "John Doe", "customerPhoneNumber": "255700000000" }
  }
}
```

`data.orderReference` is our **`Payment.external_reference`** (falls back to
`data.paymentReference`, then to the gateway `data.id` which is correlated to
`Payment.clickpesa_transaction_id`). The webhook endpoint:

1. Verifies the payload checksum (below) — unverified calls are rejected with 403.
2. Looks up the `Payment` — by our reference first, then by the stored gateway
   transaction id (`data.id`). Unknown references get 200 (a no-op) so ClickPesa
   stops retrying, but nothing is processed.
3. Is **idempotent**: if the payment is already `SUCCESSFUL`/`FAILED`/`EXPIRED`, the
   callback is acknowledged (200) and ignored. The payment row is locked
   (`select_for_update`) inside `transaction.atomic()` before any state change.
4. On `PAYMENT RECEIVED` with a matching `collectedAmount`, marks the payment
   `SUCCESSFUL`, stores the gateway transaction id + message, and calls
   `orders.services.mark_order_paid(order, actor="payment")` atomically. Amount
   mismatch → payment marked `FAILED` (reason stored), order untouched.
5. On `PAYMENT FAILED` / `PAYMENT CANCELLED`, marks the payment `FAILED`, stores
   the failure reason, and transitions the order to `PAYMENT_FAILED` (if still
   `PENDING_PAYMENT`).
6. Fires an in-app notification to the order buyer when the order transitions
   (the real-time surface the mobile app polls), plus an audit-log entry.

## Checksum / signature scheme

Webhook payloads (and API request bodies, when enabled) are signed with an HMAC-SHA256
**canonical checksum**. Algorithm (cross-language, from the official docs + demo repo):

1. **Canonicalize** the payload — recursively sort all object keys alphabetically at
   every nesting level; leave arrays in order.
2. **Serialize** — compact JSON, no whitespace (`json.dumps(..., separators=(",", ":"))`).
3. **HMAC-SHA256** the bytes with the checksum key; return the **64-char hex digest**.
4. **Exclude** the `checksum` and `checksumMethod` fields from the payload before
   computing (for validation); extract `checksumMethod` first (only `canonical` is
   supported today).

Verification compares digests with `hmac.compare_digest` (timing-safe). A missing or
mismatched checksum rejects the webhook with 403. Python implementation:

```python
import hashlib, hmac, json

def canonicalize(obj):
    if isinstance(obj, dict):
        return {k: canonicalize(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [canonicalize(v) for v in obj]
    return obj

def create_payload_checksum(key, payload):
    compact = json.dumps(canonicalize(payload), separators=(",", ":"))
    return hmac.new(key.encode(), compact.encode(), hashlib.sha256).hexdigest()

def verify_payload_checksum(key, payload):
    received = payload.get("checksum")
    body = {k: v for k, v in payload.items() if k not in ("checksum", "checksumMethod")}
    if not received:
        return False
    return hmac.compare_digest(create_payload_checksum(key, body), received)
```

Note: when checksum is enabled for an application, existing API tokens must be
regenerated (per docs). If an application is created *without* checksum enabled, it
should be enabled in the dashboard and `CLICKPESA_WEBHOOK_SECRET` set to the configured
checksum key.

## Status mapping

Remote ClickPesa statuses are folded onto **canonical** statuses
(`completed | failed | cancelled | pending`) via
`clickpesa_service.normalize_payment_status`, which recognises the many spellings
ClickPesa uses (`SUCCESS`, `PAYMENT SUCCESSFUL`, `COMPLETED`, `SETTLED`, ...;
`FAILED`, `DECLINED`, `INSUFFICIENT FUNDS`, `REVERSED`, ...; `CANCELLED`,
`ABORTED`, ...; `PENDING`, `PROCESSING`, `IN PROGRESS`, ...). The canonical value
then maps onto our payment/order state:

| Canonical status | Our `Payment.status` | Order transition |
| --- | --- | --- |
| `completed` | `SUCCESSFUL` | `PENDING_PAYMENT → PAID` (`mark_order_paid`, actor=payment) |
| `failed` / `cancelled` | `FAILED` | `PENDING_PAYMENT → PAYMENT_FAILED` |
| `pending` | `PENDING` | none (still awaiting confirmation) |
| *payment attempt superseded* | `EXPIRED` | none (a newer attempt exists) |

Each `Payment` also records `clickpesa_transaction_id` (the gateway `data.id`,
matched on later callbacks) and `failure_reason` (a human-readable message from
the gateway, e.g. "Insufficient funds", "Cancelled by user").

## Endpoints exposed by ReuseHub

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/api/payments/initiate/` | Bearer (order buyer) | Create a PENDING Payment + start a ClickPesa USSD-PUSH attempt |
| POST | `/api/payments/webhook/clickpesa/` | checksum-verified | ClickPesa callback (idempotent) |
| GET | `/api/payments/{order_id}/status/` | Bearer (order buyer) | Latest local payment + order status (polling) |
| POST | `/api/payments/{order_id}/verify/` | Bearer (order buyer) | Manual fallback: query ClickPesa directly |

## Retry semantics

A buyer may retry payment on the same order. Initiating a new attempt while the order is
`PAYMENT_FAILED` moves the order back to `PENDING_PAYMENT` (`retry_payment` transition,
actor=payment) and **expires** any older `PENDING` attempts on that order. The order can
only reach `PAID` through a verified `PAYMENT RECEIVED` webhook or a manual `verify`
against ClickPesa — never through a client-side claim.

## Reconciliation safety net (missed-webhook guarantee)

Webhooks are reliable but no gateway guarantees 100% delivery. The command:

```
python manage.py reconcile_payments [--window-minutes 5] [--max 50] [--dry-run]
```

queries ClickPesa's transaction-status API directly for any `Payment` still
`PENDING` past a short window and corrects local state to whatever the gateway
actually reports. It only touches non-terminal payments, leaves in-progress ones
alone, and applies a terminal status exactly as the webhook would (same
notifications + audit side effects). A `SELECT ... FOR UPDATE` re-check guards
against racing a webhook that arrives mid-run. Schedule it every few minutes via
cron:

```
*/5 * * * *  cd /path/backend && venv/bin/python manage.py reconcile_payments
```

## Real-time payment tracking

The mobile app tracks a payment live through two complementary surfaces:

- **Polling** — `GET /api/payments/{order_id}/status/` returns the latest local
  payment + order state; the client can poll this while the USSD prompt is on the
  user's phone.
- **In-app notifications** — when a webhook (or reconciliation) resolves a
  payment, the order transition service fires a `payment_result` notification to
  the buyer, and a `clickpesa_transaction_id`/`failure_reason` enrich the `Payment`
  record for any UI detail. Notification delivery is deferred (in-app rows now;
  Expo push tokens are a future enhancement).
