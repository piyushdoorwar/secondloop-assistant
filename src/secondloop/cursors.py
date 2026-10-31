"""Seal vendor cursors so a client cannot edit them."""

import base64
import hashlib
import hmac
import json
import os

KEY = os.environ.get(
    "CURSOR_KEY", "dev-only-cursor-key"
).encode()


def seal(case_id: str, vendor_cursor: str) -> str:
    body = json.dumps(
        {"case": case_id, "after": vendor_cursor}
    ).encode()
    tag = hmac.new(KEY, body, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(tag + body).decode()


def open_cursor(case_id: str, token: str) -> str:
    raw = base64.urlsafe_b64decode(token.encode())
    tag, body = raw[:32], raw[32:]
    good = hmac.new(KEY, body, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, good):
        raise ValueError("cursor_invalid")
    data = json.loads(body)
    if data["case"] != case_id:
        raise ValueError("cursor_invalid")
    return data["after"]
