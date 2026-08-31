# ClickPesa Payment Architecture & Integration Guide

This document is a **complete, copy-paste-ready blueprint** of the ClickPesa USSD-push
payment system as implemented in the **ReuseHub** project. You can use this file to
replicate the exact same payment flow in any other Django + React Native project.

---

## 1. Core Architecture Overview

The payment system uses an **asynchronous USSD-push model**.

1. The buyer taps "Pay Now" in the mobile app and enters their Tanzanian mobile-money number.
2. The backend sends a request to ClickPesa, which pushes a USSD PIN prompt directly to
   the customer's phone (M-Pesa, Tigo Pesa, Airtel Money, Halo Pesa).
3. Because the customer needs time to enter their PIN, the app **polls** the backend every
   few seconds while waiting.
4. ClickPesa calls your backend's **webhook URL** when the payment succeeds or fails.
5. The backend verifies the webhook checksum, marks the order `PAID`, and the app's polling
   detects the new status — showing a success modal ("Payment Received! Wait for delivery.")
   and returning the user to the order screen.

```
[Mobile App]  --POST /api/payments/initiate/--> [Django]  --HTTP--> [ClickPesa API]
                                                                           |
                                                                    (USSD push to phone)
                                                                           |
[Mobile App]  <--poll GET /api/payments/<id>/status/-- [Django]           |
                                                                           |
[Django]  <--POST /api/payments/webhook/clickpesa/-- [ClickPesa webhook]--+
```

---

## 2. Security Credentials & Environment Configuration

ClickPesa issues three critical keys. **Never** hardcode them in source code. They must
live only in the server-side `.env` file.

```env
# backend/.env  —  DO NOT COMMIT THIS FILE
CLICKPESA_BASE_URL=https://api.clickpesa.com/third-parties
CLICKPESA_CLIENT_ID=<your-client-id>
CLICKPESA_API_KEY=<your-api-key>
CLICKPESA_CHECKSUM_SECRET=<your-CHK...-key>
CLICKPESA_WEBHOOK_SECRET=<same-CHK...-key>
CLICKPESA_CURRENCY=TZS
```

| Key | What it does |
|-----|--------------|
| `CLICKPESA_CLIENT_ID` | Identifies your merchant account in every API call |
| `CLICKPESA_API_KEY` | Authorises outbound HTTP requests from Django to ClickPesa |
| `CLICKPESA_WEBHOOK_SECRET` | Used to compute & verify the HMAC-SHA256 checksum on incoming webhooks |

> **Important:** `CLICKPESA_CHECKSUM_SECRET` and `CLICKPESA_WEBHOOK_SECRET` are the
> **same value** (the `CHK...` key from the ClickPesa Dashboard → Developers → Checksum).
> The backend uses it to *compute* a hash of the incoming payload and compares it to the
> `checksum` field sent by ClickPesa. They must match for the webhook to be accepted.

---

## 3. What the Checksum Is (Common Mistake!)

A very common mistake is putting the **raw secret** (`CHKLhoTaBzIAP8xE9vwLS9BWz9SLIHGAs6Q`)
directly in the `checksum` field of a test payload. This is **wrong**.

The `checksum` field in the webhook payload is:

```
checksum = HMAC-SHA256( secret_key, canonical_JSON_of_payload )
```

The output is a **hex digest string** (e.g. `df7b00b1a97debed3d215974e6ee2e3e...`),
**not** the raw secret itself.

### Python implementation (backend — `payments/checksum.py`)

```python
import json, hmac, hashlib

def create_payload_checksum(secret: str, payload: dict) -> str:
    """
    Build the canonical JSON of `payload` (sorted keys, no spaces),
    then return its HMAC-SHA256 hex digest using `secret`.
    """
    canonical = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    return hmac.new(
        secret.encode('utf-8'),
        canonical.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
```

### Verification on incoming webhooks

```python
def verify_payload_checksum(secret: str, payload: dict) -> bool:
    provided = payload.pop('checksum', '')       # remove from payload before hashing
    expected = create_payload_checksum(secret, payload)
    return hmac.compare_digest(expected, provided)
```

---

## 4. Webhook & Callback Infrastructure

### ClickPesa Dashboard configuration

Log in to the **ClickPesa Merchant Dashboard → Developers → Webhook**.
Set the Callback URL to:

```
https://<your-public-domain>/api/payments/webhook/clickpesa/
```

The webhook URL **must be publicly reachable** (HTTPS). During local development, use ngrok
(see section 5). In production, use your actual domain name.

### Backend endpoint (Django)

```
POST /api/payments/webhook/clickpesa/
```

- No authentication required (ClickPesa has no JWT).
- Security comes entirely from the **checksum verification**.
- Returns `HTTP 200 { "status": "ok" }` on success.
- Returns `HTTP 403` if the checksum is invalid.

### Supported ClickPesa webhook payload format

```json
{
  "event": "PAYMENT RECEIVED",
  "data": {
    "orderReference": "RH064C945C990F45291",
    "status": "SUCCESSFUL",
    "collectedAmount": "500.00",
    "id": "TXN_REAL_ID",
    "phoneNumber": "255712345678"
  },
  "checksum": "<hex-digest-from-hmac-sha256>"
}
```

---

## 5. Local Development via Ngrok

ClickPesa cannot POST to `http://localhost:8000` because localhost is not reachable from
the public internet. Use ngrok to expose your local Django server.

### Step-by-step

```bash
# 1. Install ngrok (if not installed): https://ngrok.com/download
# 2. Start your Django server on ALL interfaces (not just 127.0.0.1)
python manage.py runserver 0.0.0.0:8000

# 3. In a separate terminal, start the ngrok tunnel
ngrok http 8000
# ngrok prints something like:
#   Forwarding https://oversweet-relax-wife.ngrok-free.dev -> http://127.0.0.1:8000
```

> **Critical:** Always use `python manage.py runserver 0.0.0.0:8000` (not just `runserver`).
> The default `127.0.0.1:8000` only accepts connections from the same machine; ngrok cannot
> reach it from outside.

### Set the ngrok URL in `backend/.env`

```env
NGROK_PUBLIC_URL=https://oversweet-relax-wife.ngrok-free.dev
CLICKPESA_WEBHOOK_BASE_URL=https://oversweet-relax-wife.ngrok-free.dev
```

### Add the ngrok domain to `ALLOWED_HOSTS`

```env
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,oversweet-relax-wife.ngrok-free.dev,.ngrok-free.dev,*
```

### Set the ClickPesa Dashboard webhook URL

In the ClickPesa Dashboard → Developers → Webhook, set:

```
https://oversweet-relax-wife.ngrok-free.dev/api/payments/webhook/clickpesa/
```

### Set the mobile app to use the ngrok URL

```env
# mobile/.env
EXPO_PUBLIC_API_URL=https://oversweet-relax-wife.ngrok-free.dev/api
```

> **Note:** The free tier of ngrok gives you a **new URL every time you restart ngrok**.
> Every time you restart ngrok you must update:
> 1. `backend/.env` → `NGROK_PUBLIC_URL` and `CLICKPESA_WEBHOOK_BASE_URL`
> 2. `mobile/.env` → `EXPO_PUBLIC_API_URL`
> 3. The **ClickPesa Dashboard** → Webhook Callback URL
> 4. `ALLOWED_HOSTS` in `backend/.env` (add the new ngrok domain)
> Then restart the Django server so it picks up the new values.

---

## 6. API Endpoints

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| `POST` | `/api/payments/initiate/` | JWT (buyer) | Start a USSD-push payment |
| `POST` | `/api/payments/webhook/clickpesa/` | None | ClickPesa payment callback |
| `GET`  | `/api/payments/<order_id>/status/` | JWT (buyer) | Poll payment & order status |
| `POST` | `/api/payments/<order_id>/verify/` | JWT (buyer) | Manual status fallback query to ClickPesa |

### Initiate payload

```json
{ "order_id": 42, "phone_number": "255712345678" }
```

Phone number must be a **Tanzanian number in 255XXXXXXXXX format** (no `+`).
The mobile app auto-converts `0712345678` → `255712345678`.

### Status poll response

```json
{
  "payment": {
    "status": "successful",
    "status_label": "Successful",
    "amount": "500.00",
    "external_reference": "RH064C945C990F45291",
    "transaction_id": "TXN_REAL_ID"
  },
  "order": {
    "id": 42,
    "status": "paid",
    "status_label": "Paid"
  }
}
```

---

## 7. Full Flow of Operations

```
1. Buyer taps "Pay Now" → enters phone number
2. App → POST /api/payments/initiate/  { order_id, phone_number }
3. Django creates Payment record (status=PENDING) → calls ClickPesa API
4. ClickPesa pushes USSD prompt to buyer's phone
5. App begins polling GET /api/payments/<id>/status/ (3s → 5s → 8s → 10s → 15s back-off)
6. Buyer enters PIN on their phone
7. ClickPesa → POST /api/payments/webhook/clickpesa/ (signed with HMAC-SHA256)
8. Django verifies checksum → updates Payment to SUCCESSFUL → Order to PAID
9. Next poll from app detects status=PAID → shows "Payment Received! Wait for delivery." modal (2.5s)
10. App navigates back to order screen
```

---

## 8. Testing the Webhook with Curl

Use the included helper script to generate a **valid** signed test payload:

```bash
cd backend
source myvenv/bin/activate
python test_webhook_curl.py <orderReference>
```

The script prints a ready-to-paste `curl` command with the correct HMAC-SHA256 checksum.
Copy the printed `curl` line and run it in any terminal.

**Expected Django console output on success:**

```
============================================================
  CLICKPESA WEBHOOK RECEIVED
============================================================
  Event        : PAYMENT RECEIVED
  Order Ref    : <orderReference>
  Status       : SUCCESSFUL
  Amount       : 500.00 TZS
  Checksum OK  : yes
============================================================
  ✓ PAYMENT SUCCESSFUL — Order <orderReference>
============================================================
HTTP 200 OK
```

---

## 9. Mobile UI Success Message

After a successful payment, the mobile app shows a modal with:

```
Payment Received!
ClickPesa has confirmed your payment. Your order is now being processed. Wait for delivery.
```

**To change this message**, edit line ~566 in:

```
mobile/src/screens/payment/PaymentScreen.tsx
```

Look for the `<Modal visible={showSuccess}>` block and update the `<Text style={styles.modalBody}>` content.

---

## 10. What Each Party Sees After a Successful Payment

| Party | What they see |
|-------|---------------|
| **Buyer (mobile app)** | Green success modal → "Wait for delivery." → navigated back to order (status: PAID) |
| **Seller** | Order appears in their "My Orders" screen with status **PAID** |
| **Admin** | Django Admin → Payments → status **SUCCESSFUL**; Orders → status **PAID** |

---

## 11. User Accounts for Development & Testing

| Email | Password | Role |
|-------|----------|------|
| `admin@gmail.com` | `1234` | Admin / Superuser |
| `lidyakimomwe@gmail.com` | `1234567` | Seller (staff) |
| `sadakimomwe@gmail.com` | `12345678` | Buyer |

To create or reset these accounts:

```bash
cd backend
source myvenv/bin/activate
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
