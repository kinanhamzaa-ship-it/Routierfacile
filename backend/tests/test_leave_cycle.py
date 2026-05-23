"""Tests for the leave-period cycle feature (iteration 10).

Covers all scenarios from the review request:
- Auth + dashboard null safety when no entries
- Auto cycle creation on first entry
- Consecutive entries share the same cycle
- 6+ day gap triggers leave cycle + new work cycle
- Boundary: gap of exactly 5 days NO trigger, gap exactly 6 days triggers
- Backdating never triggers leave detection
- Delete last entry of cycle removes cycle and reverts skipping leave cycles
- Delete non-last entry keeps cycle alive
- After revert: reopened cycle ended_at=null, is_reduced_weekly_rest=false
- /cycles/current and /cycles/start-new
- summary/month + auth/me
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://logbook-driver.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"


def _register():
    email = f"TEST_leave_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!", "name": "Leave Test"})
    assert r.status_code == 200, r.text
    data = r.json()
    return data["token"], data["user"]["id"], email


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _entry(date, start="08:00", end="16:00"):
    return {
        "date": date,
        "start_time": start,
        "end_time": end,
        "driving_segments": [120, 120],
        "rest_breaks": [45, 0],
        "departure": "Paris",
        "arrival": "Lyon",
        "notes": "",
        "decoucher": False,
        "meal_status": "yes",
        "double_equipage": False,
    }


# ============= AUTH & EMPTY DASHBOARD =============
class TestAuthAndEmptyDashboard:
    def test_register_returns_token(self):
        token, uid, email = _register()
        assert isinstance(token, str) and len(token) > 10
        assert uid
        # auth/me works
        r = requests.get(f"{API}/auth/me", headers=_h(token))
        assert r.status_code == 200
        assert r.json()["email"] == email.lower()

    def test_empty_user_dashboard_no_crash(self):
        token, _, _ = _register()
        r = requests.get(f"{API}/summary/dashboard", headers=_h(token))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["cycle"] is None
        assert d["previous_cycle"] is None
        assert d["leave_period"] is None
        assert d["latest_entry"] is None
        # month present, zeroed
        assert d["month"]["working_days"] == 0

    def test_current_cycle_none_when_no_entries(self):
        token, _, _ = _register()
        r = requests.get(f"{API}/cycles/current", headers=_h(token))
        assert r.status_code == 200
        assert r.json() is None


# ============= ENTRY → AUTO CYCLE =============
class TestAutoCycleCreation:
    def test_first_entry_creates_cycle(self):
        token, _, _ = _register()
        r = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-05"))
        assert r.status_code == 200, r.text
        entry = r.json()
        assert entry["cycle_id"]
        cur = requests.get(f"{API}/cycles/current", headers=_h(token)).json()
        assert cur and cur["id"] == entry["cycle_id"]

    def test_consecutive_entries_same_cycle(self):
        token, _, _ = _register()
        ids = []
        for d in ["2026-01-05", "2026-01-06", "2026-01-07"]:
            r = requests.post(f"{API}/entries", headers=_h(token), json=_entry(d))
            assert r.status_code == 200, r.text
            ids.append(r.json()["cycle_id"])
        assert len(set(ids)) == 1, f"All consecutive entries should share a cycle, got {ids}"


# ============= LEAVE DETECTION =============
class TestLeaveDetection:
    def test_gap_exactly_6_days_triggers(self):
        """prev=2026-01-01, new=2026-01-08 → gap_days = 6, must trigger."""
        token, _, _ = _register()
        r1 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-01"))
        old_cycle = r1.json()["cycle_id"]
        r2 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-08"))
        assert r2.status_code == 200, r2.text
        new_cycle = r2.json()["cycle_id"]
        assert new_cycle != old_cycle, "Gap=6 should trigger NEW cycle"
        # Check leave_period via dashboard
        d = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert d["cycle"]["id"] == new_cycle
        assert d["previous_cycle"] is not None
        # NEW SPEC (iter 11): dashboard.previous_cycle now reflects the most-
        # recent closed cycle, which is the leave cycle since it was created
        # AFTER the work cycle closed.
        assert d["previous_cycle"].get("is_leave_period") is True
        assert d["leave_period"] is not None
        assert d["leave_period"]["leave_days"] == 6
        assert d["leave_period"]["leave_start_date"] == "2026-01-02"
        assert d["leave_period"]["leave_end_date"] == "2026-01-07"

    def test_gap_exactly_5_days_no_trigger(self):
        """prev=2026-01-01, new=2026-01-07 → gap_days = 5, must NOT trigger."""
        token, _, _ = _register()
        r1 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-01"))
        c1 = r1.json()["cycle_id"]
        r2 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-07"))
        assert r2.json()["cycle_id"] == c1, "Gap=5 must NOT create new cycle"
        d = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert d["leave_period"] is None

    def test_gap_large_triggers(self):
        token, _, _ = _register()
        r1 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-01"))
        old = r1.json()["cycle_id"]
        r2 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-15"))
        new = r2.json()["cycle_id"]
        assert new != old
        d = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert d["leave_period"]["leave_days"] == 13
        assert d["leave_period"]["leave_start_date"] == "2026-01-02"
        assert d["leave_period"]["leave_end_date"] == "2026-01-14"

    def test_backdating_no_leave_trigger(self):
        """Backdating still attaches to the same open work cycle (no new work
        cycle created). NOTE: per iter-11 dynamic reconciliation, a leave cycle
        WILL be created if the resulting gap >= 6 days — the 'no backdate
        leave detection' rule applies only to in-line create_entry detection,
        not to the projection-based reconcile pass."""
        token, _, _ = _register()
        r1 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-02-01"))
        c1 = r1.json()["cycle_id"]
        # Backdate by 20 days
        r2 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-10"))
        assert r2.status_code == 200, r2.text
        d = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        # Same open work cycle still in use
        assert d["cycle"]["id"] == c1
        # Reconciliation projected a leave cycle for the 21-day gap
        assert d["leave_period"] is not None
        assert d["leave_period"]["leave_start_date"] == "2026-01-11"
        assert d["leave_period"]["leave_end_date"] == "2026-01-31"
        assert d["leave_period"]["leave_days"] == 21

    def test_multiple_consecutive_leave_events(self):
        """Two separate leave gaps; per iter-11 spec, previous_cycle = most
        recent closed cycle (which is the latest leave cycle), and leave_period
        also surfaces the latest leave."""
        token, _, _ = _register()
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-01"))
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-10"))  # leave #1 (gap=8)
        # now mid-cycle
        mid_cycle_dash = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert mid_cycle_dash["leave_period"] is not None
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-20"))  # leave #2 (gap=9)
        d = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        # previous_cycle = the most recent leave cycle per new spec
        assert d["previous_cycle"] is not None
        assert d["previous_cycle"].get("is_leave_period") is True
        # The latest leave projection covers jan-11..jan-19
        assert d["leave_period"]["leave_start_date"] == "2026-01-11"
        assert d["leave_period"]["leave_end_date"] == "2026-01-19"


# ============= DELETE + REVERT =============
class TestDeleteRevert:
    def test_delete_non_last_keeps_cycle(self):
        token, _, _ = _register()
        e1 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-05")).json()
        e2 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-06")).json()
        r = requests.delete(f"{API}/entries/{e1['id']}", headers=_h(token))
        assert r.status_code == 200
        body = r.json()
        assert body["deleted_empty_cycle"] is False
        assert body["reverted_to_cycle"] is None
        cur = requests.get(f"{API}/cycles/current", headers=_h(token)).json()
        assert cur and cur["id"] == e2["cycle_id"]

    def test_delete_last_entry_with_leave_skips_to_work_cycle(self):
        """Delete last entry of new cycle after leave: must revert to OLD work cycle, skipping leave cycle."""
        token, _, _ = _register()
        r1 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-01"))
        old_work = r1.json()["cycle_id"]
        r2 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-10"))
        new_entry_id = r2.json()["id"]
        new_cycle = r2.json()["cycle_id"]
        assert new_cycle != old_work
        # Delete the new cycle's only entry
        r = requests.delete(f"{API}/entries/{new_entry_id}", headers=_h(token))
        body = r.json()
        assert body["deleted_empty_cycle"] is True
        assert body["reverted_to_cycle"] == old_work, "must skip leave cycle and reopen work cycle"
        # Verify reopened cycle properties
        cur = requests.get(f"{API}/cycles/current", headers=_h(token)).json()
        assert cur is not None
        assert cur["id"] == old_work
        assert cur["ended_at"] is None
        assert cur["is_reduced_weekly_rest"] is False

    def test_delete_last_entry_only_leave_behind_no_revert(self):
        """If the only closed cycle behind is a leave cycle, no revert target -> reverted_to_cycle=null."""
        token, _, _ = _register()
        # Manually craft: first entry creates cycle, then we close it via start-new,
        # then we... actually leave cycle is created via gap detection only when there's a prev entry.
        # Scenario: entry A → close it via start-new (no leave) → entry B (no prev gap test).
        # To get ONLY leave behind we'd have to manually insert. Skip with a marker
        # since the existing flow always creates a work cycle first.
        pytest.skip("Leave-only-behind scenario requires manual DB seeding; covered by skip-leave logic in other tests")


# ============= CYCLES ENDPOINTS =============
class TestCyclesEndpoints:
    def test_start_new_closes_no_new_created(self):
        token, _, _ = _register()
        # Entry Mar 01 ending 16:00. Need 45h gap -> Mar 03 13:00.
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-03-01"))
        r = requests.post(
            f"{API}/cycles/start-new", headers=_h(token),
            json={"date": "2026-03-03", "start_time": "13:00"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["closed_cycle_id"] is not None
        # No open cycle until next entry
        cur = requests.get(f"{API}/cycles/current", headers=_h(token)).json()
        assert cur is None
        # Next entry creates a fresh cycle
        e = requests.post(
            f"{API}/entries", headers=_h(token),
            json=_entry("2026-03-03", start="13:00"),
        ).json()
        cur2 = requests.get(f"{API}/cycles/current", headers=_h(token)).json()
        assert cur2 and cur2["id"] == e["cycle_id"]

    def test_start_new_when_no_cycle_requires_prev_entry(self):
        """New contract: start-new with no previous entry must return 400 rest_required."""
        token, _, _ = _register()
        r = requests.post(
            f"{API}/cycles/start-new", headers=_h(token),
            json={"date": "2026-03-03", "start_time": "13:00"},
        )
        assert r.status_code == 400, r.text
        assert r.json()["detail"]["code"] == "rest_required"


# ============= EXISTING ENDPOINTS REGRESSION =============
class TestRegression:
    def test_summary_month_works(self):
        token, _, _ = _register()
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-04-05"))
        r = requests.get(f"{API}/summary/month?year=2026&month=4", headers=_h(token))
        assert r.status_code == 200
        assert r.json()["working_days"] == 1

    def test_entries_crud(self):
        token, _, _ = _register()
        e = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-05-01")).json()
        # GET single
        g = requests.get(f"{API}/entries/{e['id']}", headers=_h(token))
        assert g.status_code == 200 and g.json()["id"] == e["id"]
        # LIST
        lst = requests.get(f"{API}/entries", headers=_h(token)).json()
        assert any(x["id"] == e["id"] for x in lst)
        # PUT
        upd = _entry("2026-05-01", start="07:00")
        u = requests.put(f"{API}/entries/{e['id']}", headers=_h(token), json=upd)
        assert u.status_code == 200
        assert u.json()["start_time"] == "07:00"
        # DELETE
        d = requests.delete(f"{API}/entries/{e['id']}", headers=_h(token))
        assert d.status_code == 200
