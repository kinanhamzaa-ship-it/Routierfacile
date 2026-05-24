"""End-to-end tests for the forgot-password and delete-account features.

Tokens for forgot-password are HMAC-SHA256-hashed at rest (same pattern as
email verification), so we recover the raw token from the backend log
(SMTP is a no-op fallback in CI / preview).
"""
import os
import re
import subprocess
import time
import uuid
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


def _fresh_email(prefix="fp"):
    return f"test_{prefix}_{uuid.uuid4().hex[:8]}@example.com"


def _register_and_verify(email=None, password="Old1234!", name="FP"):
    """Use the conftest helper for a fully-verified user."""
    from conftest import register_verified_user
    if email is None:
        token, user_id, email = register_verified_user(password=password, name=name)
    else:
        # Register manually then mark verified
        r = requests.post(f"{API}/auth/register",
                          json={"email": email, "password": password, "name": name},
                          timeout=30)
        assert r.status_code == 200, r.text
        client = MongoClient(MONGO_URL)
        try:
            client[DB_NAME].users.update_one(
                {"email": email.lower().strip()},
                {"$set": {"email_verified": True}},
            )
        finally:
            client.close()
        r = requests.post(f"{API}/auth/login",
                          json={"email": email, "password": password},
                          timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        token = d["token"]
        user_id = d["user"]["id"]
    return token, user_id, email


def _grab_reset_token_from_log():
    out = subprocess.check_output(
        ["tail", "-n", "200", "/var/log/supervisor/backend.err.log"],
        timeout=5,
    ).decode()
    matches = re.findall(r"reset-password\?token=([A-Za-z0-9_-]+)", out)
    return matches[-1] if matches else None


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ============================================================
# Forgot password
class TestForgotPassword:
    def test_forgot_for_unknown_email_returns_generic_200(self):
        r = requests.post(
            f"{API}/auth/forgot-password",
            json={"email": f"nope-{uuid.uuid4().hex[:8]}@example.com"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        assert "Si un compte existe" in r.json()["message"]

    def test_forgot_for_known_email_creates_hashed_token(self):
        _, user_id, email = _register_and_verify()
        r = requests.post(
            f"{API}/auth/forgot-password",
            json={"email": email}, timeout=30,
        )
        assert r.status_code == 200
        # Token must be hashed in DB; the raw value must not appear.
        client = MongoClient(MONGO_URL)
        try:
            doc = client[DB_NAME].password_reset_tokens.find_one({"user_id": user_id})
            assert doc is not None
            assert "token_hash" in doc and isinstance(doc["token_hash"], str)
            raw = _grab_reset_token_from_log()
            assert raw
            assert doc["token_hash"] != raw, "raw token leaked into DB"
        finally:
            client.close()

    def test_forgot_within_cooldown_does_not_rotate_token(self):
        _, user_id, email = _register_and_verify()
        requests.post(f"{API}/auth/forgot-password",
                      json={"email": email}, timeout=30)
        client = MongoClient(MONGO_URL)
        try:
            hash_before = client[DB_NAME].password_reset_tokens.find_one(
                {"user_id": user_id})["token_hash"]
        finally:
            client.close()
        # Immediate second request: within the 60s cooldown
        requests.post(f"{API}/auth/forgot-password",
                      json={"email": email}, timeout=30)
        client = MongoClient(MONGO_URL)
        try:
            hash_after = client[DB_NAME].password_reset_tokens.find_one(
                {"user_id": user_id})["token_hash"]
            assert hash_after == hash_before
        finally:
            client.close()


# ============================================================
# Reset password
class TestResetPassword:
    def test_reset_with_valid_token_updates_password(self):
        token, user_id, email = _register_and_verify(password="Old1234!")
        requests.post(f"{API}/auth/forgot-password",
                      json={"email": email}, timeout=30)
        raw = _grab_reset_token_from_log()
        assert raw
        r = requests.post(f"{API}/auth/reset-password",
                          json={"token": raw, "new_password": "Brand5678!"},
                          timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        # Old password fails
        r = requests.post(f"{API}/auth/login",
                          json={"email": email, "password": "Old1234!"},
                          timeout=30)
        assert r.status_code == 401
        # New password works
        r = requests.post(f"{API}/auth/login",
                          json={"email": email, "password": "Brand5678!"},
                          timeout=30)
        assert r.status_code == 200, r.text

    def test_reset_with_invalid_token_returns_400(self):
        r = requests.post(f"{API}/auth/reset-password",
                          json={"token": "bogus-" + uuid.uuid4().hex,
                                "new_password": "Brand5678!"}, timeout=30)
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "invalid_or_expired_token"

    def test_reset_token_is_single_use(self):
        _, _, email = _register_and_verify()
        requests.post(f"{API}/auth/forgot-password",
                      json={"email": email}, timeout=30)
        raw = _grab_reset_token_from_log()
        # First use OK
        r1 = requests.post(f"{API}/auth/reset-password",
                           json={"token": raw, "new_password": "First1234!"},
                           timeout=30)
        assert r1.status_code == 200
        # Second use rejected
        r2 = requests.post(f"{API}/auth/reset-password",
                           json={"token": raw, "new_password": "Second12345!"},
                           timeout=30)
        assert r2.status_code == 400
        assert r2.json()["detail"]["code"] == "invalid_or_expired_token"

    def test_reset_with_short_password_returns_422(self):
        r = requests.post(f"{API}/auth/reset-password",
                          json={"token": "x", "new_password": "short"}, timeout=30)
        assert r.status_code == 422


# ============================================================
# Delete account
class TestDeleteAccount:
    def test_delete_with_wrong_password_returns_403(self):
        token, _, _ = _register_and_verify(password="Pass1234!")
        r = requests.request("DELETE", f"{API}/auth/me",
                             headers=_h(token),
                             json={"password": "wrong-password"}, timeout=30)
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "invalid_password"

    def test_delete_with_correct_password_returns_counts_and_purges_data(self):
        token, user_id, email = _register_and_verify(password="Pass1234!")
        # Create some user data first (entry → cycle)
        entry = {
            "date": "2026-01-01", "start_time": "06:00", "end_time": "14:00",
            "driving_segments": [240, 60], "rest_breaks": [45],
            "departure": "Paris", "arrival": "Lyon", "notes": "",
            "decoucher": False, "meal_status": "yes", "double_equipage": False,
        }
        r = requests.post(f"{API}/entries", headers=_h(token), json=entry, timeout=30)
        assert r.status_code == 200
        # Make sure they have a forgot-token too (should be wiped on delete)
        requests.post(f"{API}/auth/forgot-password",
                      json={"email": email}, timeout=30)
        # Now DELETE
        r = requests.request("DELETE", f"{API}/auth/me", headers=_h(token),
                             json={"password": "Pass1234!"}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["deleted_entries"] >= 1
        assert body["deleted_cycles"] >= 1
        # Verify everything is gone in MongoDB
        client = MongoClient(MONGO_URL)
        try:
            db = client[DB_NAME]
            assert db.users.find_one({"id": user_id}) is None
            assert db.entries.count_documents({"user_id": user_id}) == 0
            assert db.cycles.count_documents({"user_id": user_id}) == 0
            assert db.email_verification_tokens.count_documents({"user_id": user_id}) == 0
            assert db.password_reset_tokens.count_documents({"user_id": user_id}) == 0
        finally:
            client.close()

    def test_after_delete_token_is_rejected(self):
        token, _, _ = _register_and_verify(password="Pass1234!")
        r = requests.request("DELETE", f"{API}/auth/me", headers=_h(token),
                             json={"password": "Pass1234!"}, timeout=30)
        assert r.status_code == 200
        # Old JWT no longer maps to a user
        r = requests.get(f"{API}/auth/me", headers=_h(token), timeout=30)
        assert r.status_code == 401

    def test_after_delete_email_can_be_reregistered(self):
        token, _, email = _register_and_verify(password="Pass1234!")
        r = requests.request("DELETE", f"{API}/auth/me", headers=_h(token),
                             json={"password": "Pass1234!"}, timeout=30)
        assert r.status_code == 200
        # Re-register with the SAME email — should work
        r = requests.post(f"{API}/auth/register",
                          json={"email": email, "password": "Fresh1234!",
                                "name": "Reborn"}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["email_verified"] is False  # back to default

    def test_unauthenticated_delete_returns_401(self):
        r = requests.request("DELETE", f"{API}/auth/me", timeout=30,
                             headers={"Content-Type": "application/json"},
                             json={"password": "anything"})
        assert r.status_code == 401
