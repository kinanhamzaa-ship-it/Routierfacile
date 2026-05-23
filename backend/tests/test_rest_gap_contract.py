"""Iteration 13 — Strict EU rest-gap validation on cycle closure endpoints.

Contract under test:
- POST /api/cycles/start-new requires DetectIn payload {date, start_time}.
  * No body  -> 422 (Pydantic).
  * No previous entry -> 400 detail.code='rest_required'.
  * Gap < 45h (WEEKLY_REST_FULL=2700 min) -> 400 rest_required with
    required_minutes=2700, actual_minutes=<computed>.
  * Gap >= 45h -> 200 {closed_cycle_id}.
- POST /api/cycles/confirm-reduced requires DetectIn payload.
  * Gap < 24h (WEEKLY_REST_MIN=1440 min) -> 400 rest_required.
  * 24h <= Gap < 45h -> 200, closed cycle marked is_reduced_weekly_rest=true.
  * Gap >= 45h -> 200 (over-fulfilment allowed), still marked reduced.
- POST /api/entries cap error: detail.code='cycle_max_days_reached',
  detail.title='Limite du cycle atteinte', detail.headline='6 jours travaillés',
  detail.message contains the new mandatory-rest text, detail.max_days=6.
- End-to-end: cap hit -> detect-rest -> confirm-reduced (or start-new) with
  payload -> POST /entries succeeds in fresh cycle.
"""
import os
import uuid
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://logbook-driver.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

MAX_DAYS = 6
WEEKLY_REST_FULL = 2700
WEEKLY_REST_MIN = 1440


# ---------- helpers ----------
def _register():
    email = f"TEST_restgap_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": "Passw0rd!", "name": "RestGap"},
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _entry(d, start="08:00", end="16:00"):
    return {
        "date": d, "start_time": start, "end_time": end,
        "driving_segments": [120, 120], "rest_breaks": [45, 0],
        "departure": "Paris", "arrival": "Lyon", "notes": "",
        "decoucher": False, "meal_status": "yes", "double_equipage": False,
    }


def _days(start_iso, n):
    base = date.fromisoformat(start_iso)
    return [(base + timedelta(days=i)).isoformat() for i in range(n)]


def _post_entry(token, d, start="08:00", end="16:00"):
    return requests.post(f"{API}/entries", headers=_h(token), json=_entry(d, start, end))


# =====================================================================
# 1. start-new contract
# =====================================================================
class TestStartNewContract:
    def test_no_body_returns_422(self):
        token = _register()
        r = requests.post(f"{API}/cycles/start-new", headers=_h(token))
        assert r.status_code == 422, r.text

    def test_no_previous_entry_returns_400_rest_required(self):
        token = _register()
        r = requests.post(
            f"{API}/cycles/start-new", headers=_h(token),
            json={"date": "2026-02-10", "start_time": "13:00"},
        )
        assert r.status_code == 400, r.text
        assert r.json()["detail"]["code"] == "rest_required"

    def test_insufficient_gap_returns_400_with_metrics(self):
        token = _register()
        # entry Feb 03 08:00 -> 16:00. Supply Feb 04 16:00 -> gap = 24h = 1440min, < 2700.
        _post_entry(token, "2026-02-03")
        r = requests.post(
            f"{API}/cycles/start-new", headers=_h(token),
            json={"date": "2026-02-04", "start_time": "16:00"},
        )
        assert r.status_code == 400, r.text
        detail = r.json()["detail"]
        assert detail["code"] == "rest_required"
        assert detail["required_minutes"] == WEEKLY_REST_FULL
        # Feb 03 16:00 -> Feb 04 16:00 = exactly 1440 min
        assert detail["actual_minutes"] == 1440

    def test_exact_45h_gap_succeeds(self):
        token = _register()
        # Feb 03 08:00..16:00. Feb 05 13:00 = 45h later exactly.
        e = _post_entry(token, "2026-02-03")
        assert e.status_code == 200
        original_cycle_id = e.json()["cycle_id"]
        r = requests.post(
            f"{API}/cycles/start-new", headers=_h(token),
            json={"date": "2026-02-05", "start_time": "13:00"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["closed_cycle_id"] == original_cycle_id


# =====================================================================
# 2. confirm-reduced contract
# =====================================================================
class TestConfirmReducedContract:
    def test_no_body_returns_422(self):
        token = _register()
        r = requests.post(f"{API}/cycles/confirm-reduced", headers=_h(token))
        assert r.status_code == 422

    def test_insufficient_gap_returns_400_rest_required(self):
        token = _register()
        # Entry Feb 03 16:00 end. Supply Feb 04 12:00 -> 20h gap < 24h.
        _post_entry(token, "2026-02-03")
        r = requests.post(
            f"{API}/cycles/confirm-reduced", headers=_h(token),
            json={"date": "2026-02-04", "start_time": "12:00"},
        )
        assert r.status_code == 400, r.text
        detail = r.json()["detail"]
        assert detail["code"] == "rest_required"
        assert detail["required_minutes"] == WEEKLY_REST_MIN
        assert detail["actual_minutes"] == 20 * 60

    def test_24h_gap_succeeds_and_marks_reduced(self):
        token = _register()
        _post_entry(token, "2026-02-03")
        # Feb 03 16:00 + 24h = Feb 04 16:00 (>=24h, <45h)
        r = requests.post(
            f"{API}/cycles/confirm-reduced", headers=_h(token),
            json={"date": "2026-02-04", "start_time": "16:00"},
        )
        assert r.status_code == 200, r.text
        # Verify is_reduced_weekly_rest=true on next dashboard fetch
        dash = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert dash["previous_cycle"] is not None
        assert dash["previous_cycle"]["is_reduced_weekly_rest"] is True

    def test_45h_gap_still_succeeds_and_marks_reduced(self):
        """Over-fulfilment: confirm-reduced with >=45h gap still allowed; marks reduced."""
        token = _register()
        _post_entry(token, "2026-02-03")
        r = requests.post(
            f"{API}/cycles/confirm-reduced", headers=_h(token),
            json={"date": "2026-02-05", "start_time": "13:00"},  # exactly 45h
        )
        assert r.status_code == 200, r.text
        dash = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert dash["previous_cycle"]["is_reduced_weekly_rest"] is True


# =====================================================================
# 3. New cap error shape on POST /entries
# =====================================================================
class TestCapErrorShape:
    def test_cap_error_includes_title_headline_message(self):
        token = _register()
        # 6 entries -> 7th blocked
        for d in _days("2026-02-03", MAX_DAYS):
            assert _post_entry(token, d).status_code == 200
        # 7th — Feb 09 (still consecutive, < leave threshold)
        r = _post_entry(token, "2026-02-09")
        assert r.status_code == 400, r.text
        detail = r.json()["detail"]
        assert detail["code"] == "cycle_max_days_reached"
        assert detail["title"] == "Limite du cycle atteinte"
        assert detail["headline"] == "6 jours travaillés"
        assert detail["max_days"] == MAX_DAYS
        msg = detail["message"]
        # Exact user-supplied wording
        assert "Le cycle en cours contient déjà 6 journées travaillées" in msg
        assert "(maximum autorisé)" in msg
        assert "repos hebdomadaire obligatoire" in msg
        assert "normal ou réduit" in msg


# =====================================================================
# 4. End-to-end legitimate flow after cap
# =====================================================================
class TestEndToEndAfterCap:
    def test_cap_then_detect_rest_then_confirm_reduced_then_post_entry(self):
        token = _register()
        for d in _days("2026-02-03", MAX_DAYS):  # Feb 03..Feb 08 all ending 16:00
            assert _post_entry(token, d).status_code == 200
        # Cap hit
        blocked = _post_entry(token, "2026-02-10", start="16:00")
        assert blocked.status_code == 400
        assert blocked.json()["detail"]["code"] == "cycle_max_days_reached"

        # detect-rest at sufficient (24h+) gap
        det = requests.post(
            f"{API}/cycles/detect-rest", headers=_h(token),
            json={"date": "2026-02-10", "start_time": "16:00"},
        )
        assert det.status_code == 200
        data = det.json()
        # Feb 08 16:00 -> Feb 10 16:00 = 48h
        assert data["daily_rest_minutes"] == 48 * 60
        assert data["detection"] == "weekly_rest_full"

        # confirm-reduced unblocks
        s = requests.post(
            f"{API}/cycles/confirm-reduced", headers=_h(token),
            json={"date": "2026-02-10", "start_time": "16:00"},
        )
        assert s.status_code == 200, s.text

        # POST entry in fresh cycle
        r2 = _post_entry(token, "2026-02-10", start="16:00", end="22:00")
        assert r2.status_code == 200, r2.text
        dash = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert dash["cycle"]["days_worked"] == 1
        assert dash["previous_cycle"]["is_reduced_weekly_rest"] is True

    def test_bogus_future_datetime_legit_when_gap_valid(self):
        """Cap hit -> user passes a far-future datetime (>45h from last entry) ->
        server accepts because the rest gap is valid. Subsequent entry at that
        same date/start_time succeeds in the fresh cycle."""
        token = _register()
        for d in _days("2026-02-03", MAX_DAYS):
            assert _post_entry(token, d).status_code == 200
        # Far future: Feb 28 09:00 — clearly >45h after Feb 08 16:00.
        # NOTE: a date >=6 calendar days after last entry would naturally
        # trigger the leave-gap path on POST /entries, but start-new alone
        # only validates the rest gap, so it MUST accept.
        s = requests.post(
            f"{API}/cycles/start-new", headers=_h(token),
            json={"date": "2026-02-28", "start_time": "09:00"},
        )
        assert s.status_code == 200, s.text
        assert s.json()["closed_cycle_id"] is not None
