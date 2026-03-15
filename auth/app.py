"""
Openclaw Auth Validator
-----------------------
Nginx calls this service via auth_request on every /api/ hit.
We verify Telegram's HMAC-signed initData — no shared secret in client code.

Telegram initData verification spec:
  https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qs, unquote

from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]

ALLOWED_USER_IDS: set[int] = set(
    int(uid.strip())
    for uid in os.environ.get("ALLOWED_USER_IDS", "").split(",")
    if uid.strip()
)

# Reject initData older than this (replay protection)
MAX_AGE_SECONDS = 86_400  # 24 hours


def _derive_secret_key(bot_token: str) -> bytes:
    """HMAC-SHA256("WebAppData", bot_token) — per Telegram spec."""
    return hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode(),
        digestmod=hashlib.sha256,
    ).digest()


SECRET_KEY = _derive_secret_key(BOT_TOKEN)


def verify_init_data(raw: str) -> dict:
    """
    Returns the parsed user dict on success.
    Raises ValueError with reason on any failure.
    """
    # URL-decode then parse
    parsed: dict[str, str] = {
        k: v[0]
        for k, v in parse_qs(unquote(raw), keep_blank_values=True).items()
    }

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise ValueError("Missing hash field")

    # Replay protection
    auth_date = int(parsed.get("auth_date", 0))
    if time.time() - auth_date > MAX_AGE_SECONDS:
        raise ValueError("initData expired")

    # Build data-check string: sorted key=value pairs joined by \n
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

    # Compute expected hash
    expected = hmac.new(
        key=SECRET_KEY,
        msg=check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(received_hash, expected):
        raise ValueError("Signature mismatch")

    return json.loads(parsed.get("user", "{}"))


@app.route("/validate", methods=["GET", "POST"])
def validate():
    init_data = request.headers.get("X-Telegram-Init-Data", "").strip()

    if not init_data:
        return "Missing X-Telegram-Init-Data", 401

    try:
        user = verify_init_data(init_data)
    except ValueError as exc:
        return str(exc), 403

    user_id = user.get("id")
    if ALLOWED_USER_IDS and user_id not in ALLOWED_USER_IDS:
        return "User not in allowlist", 403

    # Pass user identity downstream via Nginx auth_request_set
    resp = app.make_response("OK")
    resp.headers["X-User-Id"]   = str(user_id)
    resp.headers["X-User-Name"] = user.get("first_name", "")
    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
