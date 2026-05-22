"""
Iteration 6 — Cycle counter synchronization tests.

Verifies:
- recompute_cycle_counters stores snapshot totals on the cycle doc
- POST/PUT/DELETE /api/entries triggers recompute
- GET /api/cycles/current exposes total_driving/working/rest_minutes, days_worked, decoucher_count, last_recomputed_at
- GET /api/summary/dashboard cycle.total_driving_minutes == sum of driving_segments of entries with current cycle_id
- Legacy entries (cycle_id=null) are NEVER counted in cycle.total_driving_minutes
"""
import os
import time
import requests
import pytest
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "routier_facile")


def _unique_email(prefix="cyclesync"):
    return f"TEST_{prefix}_{int(time.time() * 1000)}@example.com"


@pytest.fixture
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture
def user_token(client):
    email = _unique_email()
    r = client.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": "Driver123!", "name": "TEST CycleSync"
    })
    assert r.status_code in (200, 201), r.text
    token = r.json()["token"]
    return token, email


@pytest.fixture
def auth_client(client, user_token):
    token, _ = user_token
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def _entry_payload(date_iso, drive_minutes):
    """Create entry payload with single driving segment of `drive_minutes`, starting 08:00."""
    h = drive_minutes // 60
    m = drive_minutes % 60
    end_h = 8 + h
    end_m = m
    return {
        "date": date_iso,
        "start_time": "08:00",
        "end_time": f"{end_h:02d}:{end_m:02d}",
        "driving_segments": [drive_minutes],
        "rest_breaks": [],
        "meal_status": "yes",
        "decoucher": False,
        "notes": "",
    }


# ---------- Cycle snapshot is written by recompute ----------
class TestCycleSnapshot:
    def test_post_entry_writes_snapshot_to_cycle(self, auth_client):
        # Create entry: 3h driving
        r = auth_client.post(f"{BASE_URL}/api/entries",
                             json=_entry_payload("2030-01-05", 180))
        assert r.status_code == 200, r.text

        # Fetch current cycle, snapshot must be there
        cyc = auth_client.get(f"{BASE_URL}/api/cycles/current").json()
        assert cyc["total_driving_minutes"] == 180
        assert cyc["total_working_minutes"] == 180  # only driving here
        assert cyc["days_worked"] == 1
        assert cyc["decoucher_count"] == 0
        assert "last_recomputed_at" in cyc and cyc["last_recomputed_at"]
        # total_rest_minutes is an int >= 0
        assert isinstance(cyc.get("total_rest_minutes"), int)

    def test_dashboard_cycle_total_matches_sum_of_entries(self, auth_client):
        # Create 3 entries: 60 + 120 + 90 = 270 min
        for d, mins in [("2030-02-05", 60), ("2030-02-06", 120), ("2030-02-07", 90)]:
            r = auth_client.post(f"{BASE_URL}/api/entries", json=_entry_payload(d, mins))
            assert r.status_code == 200, r.text
        dash = auth_client.get(f"{BASE_URL}/api/summary/dashboard").json()
        assert dash["cycle"]["total_driving_minutes"] == 270
        assert dash["cycle"]["days_worked"] == 3


# ---------- PUT updates snapshot ----------
class TestUpdateUpdatesSnapshot:
    def test_put_entry_changes_total(self, auth_client):
        # Create entry with 60 min driving
        r = auth_client.post(f"{BASE_URL}/api/entries", json=_entry_payload("2030-03-05", 60))
        assert r.status_code == 200
        entry_id = r.json()["id"]
        cyc_before = auth_client.get(f"{BASE_URL}/api/cycles/current").json()
        assert cyc_before["total_driving_minutes"] == 60

        # Update to 240 min driving
        r2 = auth_client.put(f"{BASE_URL}/api/entries/{entry_id}",
                             json=_entry_payload("2030-03-05", 240))
        assert r2.status_code == 200, r2.text
        cyc_after = auth_client.get(f"{BASE_URL}/api/cycles/current").json()
        assert cyc_after["total_driving_minutes"] == 240
        # last_recomputed_at must move forward
        assert cyc_after["last_recomputed_at"] >= cyc_before["last_recomputed_at"]

        # Dashboard endpoint mirrors the same value
        dash = auth_client.get(f"{BASE_URL}/api/summary/dashboard").json()
        assert dash["cycle"]["total_driving_minutes"] == 240


# ---------- DELETE updates snapshot ----------
class TestDeleteUpdatesSnapshot:
    def test_delete_entry_decreases_total(self, auth_client):
        # Create 2 entries: 120 + 180 = 300
        r1 = auth_client.post(f"{BASE_URL}/api/entries", json=_entry_payload("2030-04-05", 120))
        r2 = auth_client.post(f"{BASE_URL}/api/entries", json=_entry_payload("2030-04-06", 180))
        assert r1.status_code == 200 and r2.status_code == 200
        eid2 = r2.json()["id"]

        cyc = auth_client.get(f"{BASE_URL}/api/cycles/current").json()
        assert cyc["total_driving_minutes"] == 300
        assert cyc["days_worked"] == 2

        # Delete second entry
        rd = auth_client.delete(f"{BASE_URL}/api/entries/{eid2}")
        assert rd.status_code == 200

        cyc2 = auth_client.get(f"{BASE_URL}/api/cycles/current").json()
        assert cyc2["total_driving_minutes"] == 120
        assert cyc2["days_worked"] == 1


# ---------- Legacy entries excluded ----------
class TestLegacyExcluded:
    def test_legacy_entry_not_counted_in_cycle(self, auth_client, user_token):
        _, email = user_token
        # Fetch user_id via /auth/me
        me = auth_client.get(f"{BASE_URL}/api/auth/me").json()
        user_id = me["id"]

        # Inject a legacy entry directly into mongo (cycle_id=None, 500 min driving)
        mongo = MongoClient(MONGO_URL)
        db = mongo[DB_NAME]
        legacy_doc = {
            "id": f"TEST_legacy_{int(time.time()*1000)}",
            "user_id": user_id,
            "cycle_id": None,
            "date": "2029-12-20",
            "start_time": "06:00",
            "end_time": "20:00",
            "driving_segments": [500],  # 500 min
            "rest_breaks": [],
            "meal_status": "yes",
            "decoucher": False,
            "notes": "",
            "daily_rest_minutes": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        db.entries.insert_one(legacy_doc)

        try:
            # Now create a CURRENT cycle entry: 100 min
            r = auth_client.post(f"{BASE_URL}/api/entries",
                                 json=_entry_payload("2030-05-05", 100))
            assert r.status_code == 200, r.text

            cyc = auth_client.get(f"{BASE_URL}/api/cycles/current").json()
            # Snapshot must show 100, NOT 600
            assert cyc["total_driving_minutes"] == 100, (
                f"Legacy entry leaked into cycle total: {cyc['total_driving_minutes']}"
            )
            assert cyc["days_worked"] == 1

            dash = auth_client.get(f"{BASE_URL}/api/summary/dashboard").json()
            assert dash["cycle"]["total_driving_minutes"] == 100
            assert dash["cycle"]["days_worked"] == 1

            # Legacy entry is still visible in /entries listing
            all_entries = auth_client.get(f"{BASE_URL}/api/entries", params={"limit": 50}).json()
            legacy_ids = [e["id"] for e in all_entries if e["id"] == legacy_doc["id"]]
            assert len(legacy_ids) == 1
            legacy_entry = next(e for e in all_entries if e["id"] == legacy_doc["id"])
            assert legacy_entry.get("is_legacy") is True
            assert legacy_entry.get("cycle_id") is None
        finally:
            db.entries.delete_many({"user_id": user_id})
            mongo.close()


# ---------- Snapshot persisted on cycle doc itself ----------
class TestCycleDocSnapshotPersistence:
    def test_cycle_doc_in_mongo_has_snapshot_fields(self, auth_client, user_token):
        # Create one entry
        r = auth_client.post(f"{BASE_URL}/api/entries",
                             json=_entry_payload("2030-06-05", 150))
        assert r.status_code == 200
        cyc = auth_client.get(f"{BASE_URL}/api/cycles/current").json()
        cycle_id = cyc["id"]

        me = auth_client.get(f"{BASE_URL}/api/auth/me").json()

        mongo = MongoClient(MONGO_URL)
        db = mongo[DB_NAME]
        try:
            doc = db.cycles.find_one({"id": cycle_id, "user_id": me["id"]})
            assert doc is not None, "Cycle doc not found in mongo"
            for field in [
                "total_driving_minutes",
                "total_working_minutes",
                "total_rest_minutes",
                "days_worked",
                "decoucher_count",
                "last_recomputed_at",
            ]:
                assert field in doc, f"Missing snapshot field {field} on cycle doc"
            assert doc["total_driving_minutes"] == 150
            assert doc["days_worked"] == 1
        finally:
            mongo.close()
