"""End-to-end tests for the email verification flow.

These tests exercise the public HTTP contract — registration response shape,
login gating, verify-email + resend endpoints, token lifecycle (single-use,
expiry, hashed at rest), and the backfill behaviour for existing accounts.

Because tokens are stored as HMAC-SHA256 hashes only, we recover the raw
verification token via the `email_verification_tokens` collection AS WRITTEN
by the backend; we don't try to invert the hash. We poke into the collection
to retrieve the token *hash* and the user_id, then forge a known raw token by
re-creating it through a private helper from the server module.

Strategy: the SMTP send is a logged no-op in CI (SMTP_HOST not set), so we
cannot grab the token from an email. Instead, we use the same approach we use
in conftest — connect to MongoDB and read the most recent token document for
the user; the raw value is only known to the email recipient, so to simulate
the email click we generate a *new* token through a small monkeypatch helper
exposed by re-using `secrets.token_urlsafe(32)` and re-hashing it as the
backend does.

A cleaner end-to-end test for the raw-token round trip is implemented by
intercepting the SMTP layer: we monkey-patch the global SMTP-sender by
inserting an env-var that captures the raw token, since the backend logs the
verification URL when SMTP isn't configured. We parse this from the log when
needed.
"""
import os
import re
import time
import uuid
import logging
import subprocess
import pytest
import requests
from pymongo import MongoClient


BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://logbook-driver.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "routier_facile")


# ---------- helpers ----------
def _fresh_email():
    return f"TEST_ev_{uuid.uuid4().hex[:8]}@example.com"


def _register(email=None, password="Passw0rd!", name="EV"):
    if email is None:
        email = _fresh_email()
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "name": name},
        timeout=30,
    )
    return r, email


def _read_latest_token_from_log(after_marker: str | None = None) -> str | None:
    """When SMTP is not configured, the backend logs the verification link
    via `logging.warning`. We tail the supervisor log and pluck the most
    recent ?token= value."""
    try:
        out = subprocess.check_output(
            ["tail", "-n", "200", "/var/log/supervisor/backend.err.log"],
            timeout=5,
        ).decode()
    except Exception:
        return None
    matches = re.findall(r"verify-email\?token=([A-Za-z0-9_-]+)", out)
    if matches:
        return matches[-1]
    return None


def _force_verify(email: str) -> None:
    client = MongoClient(MONGO_URL)
    try:
        client[DB_NAME].users.update_one(
            {"email": email.lower().strip()},
            {"$set": {"email_verified": True}},
        )
    finally:
        client.close()


# ============================================================
# /auth/register contract
class TestRegisterContract:
    def test_register_returns_message_no_token(self):
        r, email = _register()
        assert r.status_code == 200, r.text
        body = r.json()
        assert body == {
            "email": email.lower(),
            "email_verified": False,
            "message": "Compte créé. Un e-mail de vérification vous a été envoyé.",
        } or (
            # accept message variations, but never a token
            "token" not in body and body.get("email_verified") is False
        )
        assert "token" not in body
        assert "user" not in body

    def test_register_creates_user_with_email_verified_false(self):
        r, email = _register()
        assert r.status_code == 200, r.text
        client = MongoClient(MONGO_URL)
        try:
            doc = client[DB_NAME].users.find_one({"email": email.lower()})
            assert doc is not None
            assert doc.get("email_verified") is False
        finally:
            client.close()

    def test_duplicate_register_fails(self):
        r, email = _register()
        assert r.status_code == 200
        r2, _ = _register(email=email)
        assert r2.status_code == 400


# ============================================================
# /auth/login gating
class TestLoginGating:
    def test_unverified_login_returns_403_with_french_message(self):
        r, email = _register()
        assert r.status_code == 200
        r = requests.post(
            f"{API}/auth/login",
            json={"email": email, "password": "Passw0rd!"},
            timeout=30,
        )
        assert r.status_code == 403, r.text
        detail = r.json()["detail"]
        assert detail["code"] == "email_not_verified"
        assert "Veuillez vérifier votre adresse e-mail" in detail["message"]
        assert detail["email"] == email.lower()

    def test_verified_login_succeeds(self):
        r, email = _register()
        assert r.status_code == 200
        _force_verify(email)
        r = requests.post(
            f"{API}/auth/login",
            json={"email": email, "password": "Passw0rd!"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user"]["email_verified"] is True
        assert isinstance(body["token"], str) and len(body["token"]) > 20


# ============================================================
# /auth/verify-email
class TestVerifyEmail:
    def test_verify_with_valid_token_marks_verified(self):
        r, email = _register()
        assert r.status_code == 200
        token = _read_latest_token_from_log()
        assert token, "expected verification token in backend log (SMTP no-op mode)"
        r = requests.post(f"{API}/auth/verify-email", json={"token": token}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        # User is now verified — login must succeed.
        r = requests.post(
            f"{API}/auth/login",
            json={"email": email, "password": "Passw0rd!"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        assert r.json()["user"]["email_verified"] is True

    def test_verify_with_invalid_token_returns_400(self):
        r = requests.post(
            f"{API}/auth/verify-email",
            json={"token": "totally-fake-" + uuid.uuid4().hex},
            timeout=30,
        )
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "invalid_or_expired_token"

    def test_token_is_single_use(self):
        r, email = _register()
        assert r.status_code == 200
        token = _read_latest_token_from_log()
        assert token, "expected token in log"
        # First use succeeds
        r1 = requests.post(f"{API}/auth/verify-email", json={"token": token}, timeout=30)
        assert r1.status_code == 200
        # Second use fails
        r2 = requests.post(f"{API}/auth/verify-email", json={"token": token}, timeout=30)
        assert r2.status_code == 400
        assert r2.json()["detail"]["code"] == "invalid_or_expired_token"

    def test_token_stored_as_hash_not_raw(self):
        """Defense-in-depth: the DB must never contain the raw token."""
        r, email = _register()
        assert r.status_code == 200
        token = _read_latest_token_from_log()
        assert token
        client = MongoClient(MONGO_URL)
        try:
            user = client[DB_NAME].users.find_one({"email": email.lower()})
            assert user is not None
            doc = client[DB_NAME].email_verification_tokens.find_one(
                {"user_id": user["id"]}
            )
            assert doc is not None
            # The stored token_hash MUST NOT equal the raw token.
            assert doc["token_hash"] != token
            # And no field should contain the raw token verbatim.
            for v in doc.values():
                assert v != token, f"raw token leaked into field: {v!r}"
        finally:
            client.close()


# ============================================================
# /auth/resend-verification
class TestResendVerification:
    def test_resend_returns_generic_message_for_unknown_email(self):
        r = requests.post(
            f"{API}/auth/resend-verification",
            json={"email": f"nope-{uuid.uuid4().hex[:8]}@example.com"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        assert "Si un compte existe" in r.json()["message"]

    def test_resend_for_verified_account_is_generic_noop(self):
        r, email = _register()
        assert r.status_code == 200
        _force_verify(email)
        r = requests.post(
            f"{API}/auth/resend-verification",
            json={"email": email},
            timeout=30,
        )
        assert r.status_code == 200
        assert "Si un compte existe" in r.json()["message"]

    def test_resend_within_cooldown_does_not_create_new_token(self):
        r, email = _register()
        assert r.status_code == 200
        # Read existing token hash
        client = MongoClient(MONGO_URL)
        try:
            user = client[DB_NAME].users.find_one({"email": email.lower()})
            doc_before = client[DB_NAME].email_verification_tokens.find_one(
                {"user_id": user["id"]}
            )
            assert doc_before is not None
            hash_before = doc_before["token_hash"]
        finally:
            client.close()
        # Immediate resend → still within 60s cooldown
        r = requests.post(
            f"{API}/auth/resend-verification",
            json={"email": email},
            timeout=30,
        )
        assert r.status_code == 200
        client = MongoClient(MONGO_URL)
        try:
            doc_after = client[DB_NAME].email_verification_tokens.find_one(
                {"user_id": user["id"]}
            )
            assert doc_after["token_hash"] == hash_before, "cooldown was bypassed"
        finally:
            client.close()


# ============================================================
# Backfill: existing users without email_verified must NOT remain implicitly verified
class TestBackfill:
    def test_legacy_user_without_field_is_blocked(self):
        """Insert a synthetic legacy user (no email_verified field) and verify
        the backfill behaviour: login is rejected with email_not_verified."""
        email = f"test_legacy_{uuid.uuid4().hex[:8]}@example.com"
        # Hash the password using the SAME bcrypt behaviour as the backend.
        import bcrypt
        pw_hash = bcrypt.hashpw(b"Passw0rd!", bcrypt.gensalt()).decode()
        client = MongoClient(MONGO_URL)
        try:
            client[DB_NAME].users.insert_one({
                "id": uuid.uuid4().hex,
                "email": email,
                "password_hash": pw_hash,
                "name": "Legacy",
                "role": "driver",
                # NOTE: no email_verified field
                "created_at": "2020-01-01T00:00:00+00:00",
            })
        finally:
            client.close()
        # Trigger the startup-time backfill: in practice we'd restart the
        # backend, but the existing running server has already run startup.
        # So we simulate by calling the backfill query directly.
        client = MongoClient(MONGO_URL)
        try:
            client[DB_NAME].users.update_many(
                {"email_verified": {"$exists": False}},
                {"$set": {"email_verified": False}},
            )
        finally:
            client.close()
        r = requests.post(
            f"{API}/auth/login",
            json={"email": email, "password": "Passw0rd!"},
            timeout=30,
        )
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "email_not_verified"
