import base64
import hashlib
import hmac
import json
import os
from typing import Dict, Any

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def _b64decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def sign_payload(payload: Dict[str, Any]) -> str:
    secret = os.environ.get("LICENSE_SECRET", "").encode("utf-8")
    if not secret:
        raise RuntimeError("LICENSE_SECRET env var missing.")

    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(secret, body, hashlib.sha256).digest()
    return f"{_b64(body)}.{_b64(sig)}"

def verify_token(token: str) -> Dict[str, Any]:
    secret = os.environ.get("LICENSE_SECRET", "").encode("utf-8")
    if not secret:
        raise RuntimeError("LICENSE_SECRET env var missing.")

    parts = token.split(".")
    if len(parts) != 2:
        raise ValueError("Invalid token format.")

    body_b64, sig_b64 = parts
    body = _b64decode(body_b64)
    sig = _b64decode(sig_b64)

    expected = hmac.new(secret, body, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Bad signature.")

    return json.loads(body.decode("utf-8"))