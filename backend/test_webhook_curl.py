#!/usr/bin/env python3
"""
Generate a ClickPesa webhook payload with a valid checksum and print a ready‑to‑use curl command.

Usage:
    python test_webhook_curl.py <orderReference>
"""

import sys, json, os
import django

# --------------------------------------------------------------
# Load Django settings – we need the secret and the ngrok URL.
# --------------------------------------------------------------
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from payments.checksum import create_payload_checksum

def build_payload(order_ref: str) -> dict:
    """Create the ClickPesa payload **without** the checksum field."""
    return {
        "event": "PAYMENT RECEIVED",
        "data": {
            "orderReference": order_ref,
            "status": "SUCCESSFUL",
            "collectedAmount": "500.00",
            "id": "TXN_TEST_12345",
            "phoneNumber": "255712345678",
        },
    }

def add_checksum(payload: dict) -> dict:
    """Calculate HMAC‑SHA256 checksum using the secret and insert it."""
    secret = settings.CLICKPESA_WEBHOOK_SECRET
    payload["checksum"] = create_payload_checksum(secret, payload)
    return payload

def main():
    if len(sys.argv) != 2:
        print("Usage: python test_webhook_curl.py <orderReference>")
        sys.exit(1)

    order_ref = sys.argv[1]
    payload = add_checksum(build_payload(order_ref))
    json_body = json.dumps(payload)

    # Build the full endpoint URL (ngrok base + API path)
    base_url = getattr(settings, "NGROK_PUBLIC_URL", settings.CLICKPESA_WEBHOOK_BASE_URL)
    endpoint = f"{base_url.rstrip('/')}/api/payments/webhook/clickpesa/"

    curl_cmd = (
        f"curl -i -X POST {endpoint} \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -d '{json_body}'"
    )

    print("\n--- TEST CURL COMMAND ---")
    print(curl_cmd)
    print("-------------------------\n")
    print("Payload (for reference):")
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    main()
