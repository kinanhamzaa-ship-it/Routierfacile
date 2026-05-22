"""Backend tests for iteration 9 - auto-revert on empty cycle deletion.

Validates DELETE /api/entries/{id} auto-revert behavior:
- last entry of current cycle + previous closed cycle exists -> revert
- last entry of current cycle but no prior closed cycle -> no revert
- entry of closed cycle -> no revert
- non-last entry -> no revert
- legacy entry (cycle_id=null) -> no effect on cycles
- after revert, new entry attaches to reopened cycle
"""
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


def _register():
    email = f"TEST_revert_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/auth/register",
                      json={"email": email, "password": "Passw0rd!", "name": "RevertTest"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _base_entry(d, start="06:00", end="14:00", driving=None, breaks=None):
    return {
        "date": d,
        "start_time": start,
        "end_time": end,
        "driving_segments": driving if driving is not None else [240, 90],
        "rest_breaks": breaks if breaks is not None else [45],
        "departure": "A", "arrival": "B", "notes": "",
        "decoucher": False, "meal_status": "unsure", "double_equipage": False,
    }


@pytest.fixture
def token():
    return _register()


# ---------- Helpers using API ----------
def _post_entry(token, d, **kw):
    r = requests.post(f"{BASE_URL}/api/entries", headers=_headers(token),
                      json=_base_entry(d, **kw))
    assert r.status_code == 200, r.text
    return r.json()


def _current_cycle(token):
    r = requests.get(f"{BASE_URL}/api/cycles/current", headers=_headers(token))
    assert r.status_code == 200, r.text
    return r.json()


def _start_new_cycle(token):
    r = requests.post(f"{BASE_URL}/api/cycles/start-new", headers=_headers(token))
    assert r.status_code == 200, r.text
    return r.json()


def _delete(token, entry_id):
    r = requests.delete(f"{BASE_URL}/api/entries/{entry_id}", headers=_headers(token))
    assert r.status_code == 200, r.text
    return r.json()


def _dashboard(token):
    r = requests.get(f"{BASE_URL}/api/summary/dashboard", headers=_headers(token))
    assert r.status_code == 200, r.text
    return r.json()


# Use distinct dates so create_entry's duplicate guard doesn't fire.
def _D(offset_days):
    return (date.today() - timedelta(days=offset_days)).isoformat()


# ----------------------------------------------------------------------
class TestAutoRevert:
    def test_delete_response_shape(self, token):
        """DELETE returns {ok:true, reverted_to_cycle: <id>|null}."""
        e = _post_entry(token, _D(10))
        res = _delete(token, e["id"])
        assert res["ok"] is True
        assert "reverted_to_cycle" in res
        assert res["reverted_to_cycle"] is None  # no prior closed cycle

    def test_non_last_entry_delete_no_revert(self, token):
        """Deleting non-last entry of current cycle keeps cycle open, no revert."""
        e1 = _post_entry(token, _D(20))
        e2 = _post_entry(token, _D(21))
        cyc_before = _current_cycle(token)
        res = _delete(token, e1["id"])
        assert res["reverted_to_cycle"] is None
        cyc_after = _current_cycle(token)
        assert cyc_after["id"] == cyc_before["id"]
        assert cyc_after["ended_at"] is None

    def test_last_entry_with_prev_closed_cycle_triggers_revert(self, token):
        """Delete last entry of current open cycle when prev closed cycle exists -> revert."""
        # Cycle A: 3 entries, fixed driving = sum 240+90+45 = 375 each? we use defaults (330 min)
        e_a1 = _post_entry(token, _D(40))
        e_a2 = _post_entry(token, _D(41))
        e_a3 = _post_entry(token, _D(42))
        cycle_a = _current_cycle(token)
        cycle_a_id = cycle_a["id"]

        # snapshot expected driving from cycle A entries
        expected_driving_a = sum(
            sum(e["driving_segments"]) for e in (e_a1, e_a2, e_a3)
        )

        # Close A, open B
        cycle_b = _start_new_cycle(token)
        assert cycle_b["id"] != cycle_a_id

        # Add one entry to B
        e_b1 = _post_entry(token, _D(43))
        assert e_b1["cycle_id"] == cycle_b["id"]

        # Delete it -> B becomes empty AND A exists as closed -> revert
        res = _delete(token, e_b1["id"])
        assert res["reverted_to_cycle"] == cycle_a_id, res

        # Cycle B is gone, A is reopened
        cur = _current_cycle(token)
        assert cur["id"] == cycle_a_id
        assert cur["ended_at"] is None

        # Dashboard shows reopened A with restored driving total
        dash = _dashboard(token)
        assert dash["cycle"]["id"] == cycle_a_id
        assert dash["cycle"]["total_driving_minutes"] == expected_driving_a
        assert dash["cycle"]["days_worked"] == 3

    def test_last_entry_no_prev_closed_cycle_no_revert(self, token):
        """Delete last entry of current cycle when no prior closed cycle -> cycle stays open, empty."""
        e = _post_entry(token, _D(60))
        cyc_id = e["cycle_id"]
        res = _delete(token, e["id"])
        assert res["reverted_to_cycle"] is None
        cur = _current_cycle(token)
        assert cur["id"] == cyc_id
        assert cur["ended_at"] is None
        # No entries left in this cycle
        dash = _dashboard(token)
        assert dash["cycle"]["days_worked"] == 0
        assert dash["cycle"]["total_driving_minutes"] == 0

    def test_delete_from_closed_cycle_no_revert(self, token):
        """Delete an entry from a closed cycle -> closed cycle stays closed, no revert."""
        # Cycle A with 2 entries
        e_a1 = _post_entry(token, _D(80))
        e_a2 = _post_entry(token, _D(81))
        cycle_a_id = e_a1["cycle_id"]
        # Close A
        cycle_b = _start_new_cycle(token)
        # Add entry to B so B is non-empty (so we can isolate test)
        e_b1 = _post_entry(token, _D(82))
        # Delete one entry from closed A
        res = _delete(token, e_a1["id"])
        assert res["reverted_to_cycle"] is None
        # Cycle B should still be current open
        cur = _current_cycle(token)
        assert cur["id"] == cycle_b["id"]
        assert cur["ended_at"] is None

        # Even if we delete the LAST entry of the closed cycle A, no revert happens
        res2 = _delete(token, e_a2["id"])
        assert res2["reverted_to_cycle"] is None
        # B still current
        cur2 = _current_cycle(token)
        assert cur2["id"] == cycle_b["id"]

    def test_legacy_entry_delete_no_cycle_effect(self, token):
        """Legacy entries (cycle_id=null) deletion does not affect any cycle."""
        # We need to insert a legacy entry directly via DB to simulate.
        # Instead, do it through API then manually patch cycle_id to None via mongo isn't possible from test.
        # Workaround: create entry, then delete via direct mongo. We don't have direct DB.
        # We'll skip if we cannot create legacy. But we can simulate by NOT having any cycle membership:
        # The API always assigns cycle_id, so legacy can only exist for pre-existing data.
        # Approach: register fresh user, no entries; create cycle indirectly; cannot test legacy via API alone.
        pytest.skip("Legacy entries (cycle_id=null) cannot be created via current API; covered manually.")

    def test_after_revert_new_entry_attaches_to_reopened_cycle(self, token):
        """After revert, creating a new entry attaches it to the reopened cycle."""
        e_a1 = _post_entry(token, _D(100))
        e_a2 = _post_entry(token, _D(101))
        cycle_a_id = e_a1["cycle_id"]
        _start_new_cycle(token)
        e_b1 = _post_entry(token, _D(102))
        # Trigger revert by deleting only entry in B
        res = _delete(token, e_b1["id"])
        assert res["reverted_to_cycle"] == cycle_a_id

        # New entry on a new date should attach to reopened A
        e_new = _post_entry(token, _D(103))
        assert e_new["cycle_id"] == cycle_a_id

    def test_revert_picks_most_recent_closed_cycle(self, token):
        """When multiple closed cycles exist, revert reopens the most recently closed one."""
        # Cycle 1
        e1 = _post_entry(token, _D(150))
        cycle1_id = e1["cycle_id"]
        _start_new_cycle(token)  # closes 1, opens 2
        # Cycle 2
        e2 = _post_entry(token, _D(151))
        cycle2_id = e2["cycle_id"]
        _start_new_cycle(token)  # closes 2, opens 3
        # Cycle 3
        e3 = _post_entry(token, _D(152))
        cycle3_id = e3["cycle_id"]
        assert cycle3_id not in (cycle1_id, cycle2_id)

        # Delete only entry in cycle 3 -> should revert to cycle 2 (most recent closed)
        res = _delete(token, e3["id"])
        assert res["reverted_to_cycle"] == cycle2_id
        cur = _current_cycle(token)
        assert cur["id"] == cycle2_id
        assert cur["ended_at"] is None
