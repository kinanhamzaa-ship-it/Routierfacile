"""Backend tests for Routier Facile API."""
import os
import uuid
import pytest
import requests
from datetime import date, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    # fall back to reading frontend env
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
    def test_register_returns_user_and_token(self, new_user):
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


# ---------- Entries ----------
class TestEntries:
    @pytest.fixture(scope="class")
    def headers(self, new_user):
        return {"Authorization": f"Bearer {new_user['token']}"}

    def test_create_entry_with_computed_fields(self, headers):
        today = date.today().isoformat()
        payload = {
            "date": today,
            "start_time": "06:00",
            "end_time": "18:00",
            "driving_segments": [240, 180],  # 7h
            "rest_breaks": [45, 30],  # 75 min
            "departure": "Paris",
            "arrival": "Lyon",
            "notes": "Test",
            "decoucher": True,
            "meal_status": "yes",
        }
        r = requests.post(f"{BASE_URL}/api/entries", json=payload, headers=headers)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total_driving_minutes"] == 420
        assert d["total_rest_minutes"] == 75
        assert d["amplitude_minutes"] == 720  # 12h
        assert d["total_working_minutes"] == 720 - 75
        pytest.entry_id = d["id"]

    def test_duplicate_date_returns_400(self, headers):
        today = date.today().isoformat()
        payload = {"date": today, "start_time": "07:00", "end_time": "17:00",
                   "driving_segments": [60], "rest_breaks": [30],
                   "decoucher": False, "meal_status": "no"}
        r = requests.post(f"{BASE_URL}/api/entries", json=payload, headers=headers)
        assert r.status_code == 400

    def test_list_entries(self, headers):
        r = requests.get(f"{BASE_URL}/api/entries", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list) and len(r.json()) >= 1

    def test_update_entry(self, headers):
        eid = pytest.entry_id
        today = date.today().isoformat()
        new_payload = {
            "date": today, "start_time": "06:00", "end_time": "20:00",
            "driving_segments": [300], "rest_breaks": [60],
            "departure": "Paris", "arrival": "Marseille",
            "notes": "Updated", "decoucher": False, "meal_status": "no",
        }
        r = requests.put(f"{BASE_URL}/api/entries/{eid}", json=new_payload, headers=headers)
        assert r.status_code == 200
        d = r.json()
        assert d["total_driving_minutes"] == 300
        assert d["amplitude_minutes"] == 14 * 60
        # verify persistence
        g = requests.get(f"{BASE_URL}/api/entries/{eid}", headers=headers)
        assert g.status_code == 200
        assert g.json()["arrival"] == "Marseille"

    def test_summary_week(self, headers):
        r = requests.get(f"{BASE_URL}/api/summary/week", headers=headers)
        assert r.status_code == 200
        d = r.json()
        for k in ["total_driving_minutes", "weekly_limit_minutes", "remaining_minutes", "status"]:
            assert k in d
        assert d["weekly_limit_minutes"] == 56 * 60
        assert d["status"] in ["green", "orange", "red"]

    def test_summary_month(self, headers):
        today = date.today()
        r = requests.get(f"{BASE_URL}/api/summary/month",
                         params={"year": today.year, "month": today.month},
                         headers=headers)
        assert r.status_code == 200
        d = r.json()
        assert "meal_counts" in d and set(d["meal_counts"].keys()) == {"yes", "no", "unsure"}
        assert "decoucher_count" in d

    def test_summary_dashboard(self, headers):
        r = requests.get(f"{BASE_URL}/api/summary/dashboard", headers=headers)
        assert r.status_code == 200
        d = r.json()
        assert "week" in d and "month" in d and "daily_rest_status" in d
        assert d["daily_rest_status"] in ["green", "orange", "red"]

    def test_delete_entry(self, headers):
        eid = pytest.entry_id
        r = requests.delete(f"{BASE_URL}/api/entries/{eid}", headers=headers)
        assert r.status_code == 200
        g = requests.get(f"{BASE_URL}/api/entries/{eid}", headers=headers)
        assert g.status_code == 404
