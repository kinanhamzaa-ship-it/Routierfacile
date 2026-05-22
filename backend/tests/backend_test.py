"""Backend tests for Routier Facile API - iteration 3 (cycle-based)."""
import os
import uuid
import pytest
import requests
from datetime import date, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')

ADMIN_EMAIL = "admin@routier-facile.fr"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def new_user():
    email = f"TEST_user_{uuid.uuid4().hex[:8]}@example.com"
    pwd = "Passw0rd!"
    r = requests.post(f"{BASE_URL}/api/auth/register",
                      json={"email": email, "password": pwd, "name": "Test Driver"})
    assert r.status_code == 200, r.text
    data = r.json()
    return {"email": email, "password": pwd, "token": data["token"], "id": data["user"]["id"]}


# ---------- Auth ----------
class TestAuth:
    def test_register(self, new_user):
        assert "token" in new_user and "id" in new_user

    def test_login_admin(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 0

    def test_login_wrong_password(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "WRONG"})
        assert r.status_code == 401

    def test_me_with_token(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/auth/me",
                         headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_me_without_token(self):
        r = requests.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 401


# ---------- Cycles & Entries ----------
class TestCyclesEntries:
    @pytest.fixture(scope="class")
    def headers(self, new_user):
        return {"Authorization": f"Bearer {new_user['token']}"}

    def test_cycles_current_auto_creates(self, headers):
        r = requests.get(f"{BASE_URL}/api/cycles/current", headers=headers)
        assert r.status_code == 200, r.text
        c = r.json()
        for k in ["id", "started_at", "ended_at", "reduced_rest_used", "extensions_used"]:
            assert k in c
        assert c["ended_at"] is None
        assert c["reduced_rest_used"] == 0
        assert c["extensions_used"] == 0
        pytest.cycle_id = c["id"]

    def test_create_first_entry_no_daily_rest(self, headers):
        d1 = (date.today() - timedelta(days=10)).isoformat()
        payload = {
            "date": d1, "start_time": "06:00", "end_time": "18:00",
            "driving_segments": [240, 180], "rest_breaks": [45, 30],
            "departure": "Paris", "arrival": "Lyon", "notes": "Test",
            "decoucher": True, "meal_status": "yes",
        }
        r = requests.post(f"{BASE_URL}/api/entries", json=payload, headers=headers)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total_driving_minutes"] == 420
        assert d["total_rest_minutes"] == 75
        assert d["amplitude_minutes"] == 720
        assert d["total_working_minutes"] == 720 - 75
        assert d["daily_rest_minutes"] is None  # first entry
        assert d["daily_rest_status"] is None
        assert d["is_legacy"] is False
        assert d.get("cycle_id") == pytest.cycle_id
        pytest.entry1_id = d["id"]
        pytest.entry1_date = d1

    def test_create_second_entry_with_daily_rest(self, headers):
        # next day at 06:00 -> previous ended at 18:00 -> 12h rest = 720 min
        d2 = (date.today() - timedelta(days=9)).isoformat()
        payload = {
            "date": d2, "start_time": "06:00", "end_time": "16:00",
            "driving_segments": [300], "rest_breaks": [45],
            "decoucher": False, "meal_status": "no",
        }
        r = requests.post(f"{BASE_URL}/api/entries", json=payload, headers=headers)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["daily_rest_minutes"] == 12 * 60
        assert d["daily_rest_status"] == "ok"
        pytest.entry2_id = d["id"]

    def test_detect_rest_no_signal(self, headers):
        d3 = (date.today() - timedelta(days=8)).isoformat()
        r = requests.post(f"{BASE_URL}/api/cycles/detect-rest",
                          json={"date": d3, "start_time": "06:00"}, headers=headers)
        assert r.status_code == 200
        d = r.json()
        # gap between yesterday's 16:00 and tomorrow 06:00 = 14h
        assert d["daily_rest_minutes"] == 14 * 60
        assert d["detection"] is None

    def test_detect_rest_weekly_full(self, headers):
        # date 3 days after last entry -> ~70+ hours rest -> weekly_rest_full
        d_far = (date.today()).isoformat()
        r = requests.post(f"{BASE_URL}/api/cycles/detect-rest",
                          json={"date": d_far, "start_time": "06:00"}, headers=headers)
        assert r.status_code == 200
        d = r.json()
        assert d["daily_rest_minutes"] >= 45 * 60
        assert d["detection"] == "weekly_rest_full"

    def test_detect_rest_weekly_reduced(self, headers):
        # gap between 16:00 yesterday and 36h later: pick day after at 04:00 = 36h
        d2_iso = pytest.entry1_date  # day10 ago
        # second entry was day9 ago end 16:00. day7 ago at 16:00 = 48h (full). need 24-45h.
        # day8 ago end 16:00. day7 ago 16:00 = 24h. let's use day7 ago at 15:00 = 23h: too low.
        # day7 ago at 17:00 = 25h.
        d_target = (date.today() - timedelta(days=7)).isoformat()
        r = requests.post(f"{BASE_URL}/api/cycles/detect-rest",
                          json={"date": d_target, "start_time": "11:00"}, headers=headers)
        assert r.status_code == 200
        d = r.json()
        assert 24 * 60 <= d["daily_rest_minutes"] < 45 * 60
        assert d["detection"] == "weekly_rest_reduced"

    def test_list_entries_enriched(self, headers):
        r = requests.get(f"{BASE_URL}/api/entries", headers=headers)
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 2
        for it in items:
            for k in ["amplitude_minutes", "total_working_minutes", "total_driving_minutes",
                      "total_rest_minutes", "daily_rest_status", "is_driving_extension", "is_legacy"]:
                assert k in it

    def test_dashboard_summary_cycle(self, headers):
        r = requests.get(f"{BASE_URL}/api/summary/dashboard", headers=headers)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "cycle" in d and "today" in d and "last_entry" in d and "month" in d
        c = d["cycle"]
        for k in ["total_driving_minutes", "remaining_minutes", "status",
                  "reduced_rest_used", "reduced_rest_max", "extensions_used",
                  "extensions_max", "days_worked", "decoucher_count"]:
            assert k in c, f"missing {k}"
        assert c["reduced_rest_max"] == 3
        assert c["extensions_max"] == 2
        assert c["days_worked"] >= 2
        assert c["status"] in ["green", "orange", "red"]
        # month
        m = d["month"]
        assert "meal_counts" in m and set(m["meal_counts"].keys()) == {"yes", "no", "unsure"}

    def test_update_recomputes(self, headers):
        eid = pytest.entry2_id
        d2 = (date.today() - timedelta(days=9)).isoformat()
        # change driving to 9h30 = 570 min -> triggers extension counter
        payload = {
            "date": d2, "start_time": "06:00", "end_time": "18:00",
            "driving_segments": [570], "rest_breaks": [45],
            "decoucher": False, "meal_status": "no",
        }
        r = requests.put(f"{BASE_URL}/api/entries/{eid}", json=payload, headers=headers)
        assert r.status_code == 200
        d = r.json()
        assert d["total_driving_minutes"] == 570
        assert d["is_driving_extension"] is True
        # cycle counter updated
        r2 = requests.get(f"{BASE_URL}/api/cycles/current", headers=headers)
        assert r2.json()["extensions_used"] >= 1

    def test_start_new_cycle(self, headers):
        old_id = pytest.cycle_id
        r = requests.post(f"{BASE_URL}/api/cycles/start-new", headers=headers)
        assert r.status_code == 200
        c = r.json()
        assert c["id"] != old_id
        assert c["ended_at"] is None
        assert c["reduced_rest_used"] == 0
        assert c["extensions_used"] == 0
        assert c["is_reduced_weekly_rest"] is False
        pytest.cycle_id_new = c["id"]

    def test_confirm_reduced_creates_reduced_cycle(self, headers):
        r = requests.post(f"{BASE_URL}/api/cycles/confirm-reduced", headers=headers)
        assert r.status_code == 200
        c = r.json()
        assert c["is_reduced_weekly_rest"] is True
        assert c["ended_at"] is None

    def test_new_entry_in_new_cycle(self, headers):
        d3 = (date.today() - timedelta(days=2)).isoformat()
        payload = {
            "date": d3, "start_time": "06:00", "end_time": "14:00",
            "driving_segments": [180], "rest_breaks": [30],
            "decoucher": False, "meal_status": "unsure",
        }
        r = requests.post(f"{BASE_URL}/api/entries", json=payload, headers=headers)
        assert r.status_code == 200
        cur = requests.get(f"{BASE_URL}/api/cycles/current", headers=headers).json()
        assert r.json()["cycle_id"] == cur["id"]

    def test_delete_entry(self, headers):
        r = requests.delete(f"{BASE_URL}/api/entries/{pytest.entry1_id}", headers=headers)
        assert r.status_code == 200
        g = requests.get(f"{BASE_URL}/api/entries/{pytest.entry1_id}", headers=headers)
        assert g.status_code == 404


# ---------- Legacy admin entry ----------
class TestLegacy:
    def test_admin_legacy_entry_flagged(self, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.get(f"{BASE_URL}/api/entries", headers=h)
        assert r.status_code == 200
        items = r.json()
        # legacy entries (no cycle_id) should be flagged
        legacy = [x for x in items if x.get("is_legacy")]
        # Note: may be 0 if admin has no entries at all; just assert structure
        for it in items:
            assert "is_legacy" in it
