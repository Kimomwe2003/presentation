"""ClickPesa payload checksum (canonical HMAC-SHA256) — see docs/CLICKPESA_INTEGRATION.md.

Implements the exact algorithm from the official docs (recursively sort object
keys, compact JSON, HMAC-SHA256 hex digest). Used to verify inbound webhook
payloads and to sign outbound request bodies when the app has checksum enabled.
"""

import hashlib
import hmac
import json

EXCLUDED_FIELDS = ("checksum", "checksumMethod")


def canonicalize(obj):
    """Recursively sort dict keys; leave lists and scalars untouched."""
    if isinstance(obj, dict):
        return {key: canonicalize(obj[key]) for key in sorted(obj)}
    if isinstance(obj, list):
        return [canonicalize(item) for item in obj]
    return obj


def create_payload_checksum(checksum_key: str, payload: dict) -> str:
    canonical = canonicalize(payload)
    compact = json.dumps(canonical, separators=(",", ":"))
    digest = hmac.new(
        checksum_key.encode("utf-8"),
        compact.encode("utf-8"),
        hashlib.sha256,
    )
    return digest.hexdigest()


def verify_payload_checksum(checksum_key: str, payload: dict) -> bool:
    """Return True when *payload*'s checksum matches the recomputed digest."""
    if not isinstance(payload, dict) or not checksum_key:
        return False

    # 1. Try top-level checksum (standard ClickPesa webhook)
    received = payload.get("checksum")
    if isinstance(received, str) and received:
        body = {k: v for k, v in payload.items() if k not in EXCLUDED_FIELDS}
        computed = create_payload_checksum(checksum_key, body)
        if hmac.compare_digest(computed, received):
            return True

    # 2. Try nested data checksum (alternative ClickPesa payload wrapper)
    data = payload.get("data")
    if isinstance(data, dict):
        received_nested = data.get("checksum")
        if isinstance(received_nested, str) and received_nested:
            nested_body = {k: v for k, v in data.items() if k not in EXCLUDED_FIELDS}
            computed_nested = create_payload_checksum(checksum_key, nested_body)
            if hmac.compare_digest(computed_nested, received_nested):
                return True

    return False
