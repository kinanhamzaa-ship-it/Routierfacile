"""Shared pytest fixtures for the Routier Facile backend tests.

Provides a `register_verified_user(email, password, name)` helper that
performs the new email-verification dance for tests:

1. POST /auth/register (no token returned anymore)
2. Flip `email_verified=True` directly in MongoDB (the raw token is
   unrecoverable from its hash, so we just mark the user verified —
   the verification flow itself is covered by `test_email_verification.py`).
3. POST /auth/login → returns the auth token.

Tests should call `register_verified_user` (or the `verified_user`
fixture) instead of POSTing to `/auth/register` directly.
"""
import os
import uuid as _uuid
from urllib.parse import quote_plus

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


def _verify_user_in_db(email: str) -> None:
    client = MongoClient(MONGO_URL)
    try:
        client[DB_NAME].users.update_one(
            {"email": email.lower().strip()},
            {"$set": {"email_verified": True}},
        )
    finally:
        client.close()


def register_verified_user(email: str | None = None, password: str = "Passw0rd!",
                           name: str = "Test"):
    """Register, mark verified, and log in. Returns (token, user_id, email)."""
    if email is None:
        email = f"TEST_{_uuid.uuid4().hex[:10]}@example.com"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "name": name},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    _verify_user_in_db(email)
    r = requests.post(
        f"{API}/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    return data["token"], data["user"]["id"], email


@pytest.fixture
def verified_user():
    """Pytest fixture wrapper around register_verified_user."""
    return register_verified_user()
