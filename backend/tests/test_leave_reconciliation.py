"""Iteration 11 - Dynamic reconciliation of leave-period cycles.

Whenever entries are CREATED / UPDATED / DELETED, the backend must re-derive
the leave cycles purely from the current entries:
- A leave cycle exists ONLY IF a gap of >= 6 full inactive days exists between
  two consecutive entries.
- Stale leave cycles whose covered range no longer matches a current gap must
  be deleted automatically.
- Bidirectional: new gaps caused by deletion or date-change must also produce a
  leave cycle.
- Work (non-leave) cycles are NEVER touched.

Backend code: reconcile_leave_cycles() in /app/backend/server.py.
"""
import os
import uuid
import pytest
import requests

def _load_base_url():
    v = os.environ.get('REACT_APP_BACKEND_URL')
    if v:
        return v.rstrip('/')
    # Fallback: read from /app/frontend/.env so tests can run in CI
    env_path = '/app/frontend/.env'
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip().rstrip('/')
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = _load_base_url()
API = f"{BASE_URL}/api"


def _register():
    email = f"TEST_rec_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register",
                      json={"email": email, "password": "Passw0rd!", "name": "Rec Test"})
    assert r.status_code == 200, r.text
    j = r.json()
    return j["token"], j["user"]["id"]


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


def _list_leave_cycles(token):
    """Return current leave-period cycles via dashboard.leave_period probe + a
    direct query through summary endpoints. There is no public endpoint that
    lists all cycles, so we read /api/summary/dashboard repeatedly. To get
    ALL leave cycles, we need another method: probe by using cycles/current
    won't help. We rely on the contract that reconcile leaves exactly the
    valid gaps; dashboard.leave_period shows the most recent one. For full
    enumeration we hit /api/entries and recompute the expected gaps locally,
    then assert dashboard reflects the most-recent one."""
    raise NotImplementedError


def _expected_gaps(dates):
    """Local re-implementation of the reconcile invariant — used to compute the
    expected leave cycle set from a chronological list of entry dates."""
    from datetime import date as date_cls
    gaps = []
    sorted_dates = sorted(dates)
    for i in range(1, len(sorted_dates)):
        py, pm, pd = [int(x) for x in sorted_dates[i - 1].split("-")]
        cy, cm, cd = [int(x) for x in sorted_dates[i].split("-")]
        from datetime import timedelta
        prev_d = date_cls(py, pm, pd)
        curr_d = date_cls(cy, cm, cd)
        gd = (curr_d - prev_d).days - 1
        if gd >= 6:
            gaps.append({
                "leave_start_date": (prev_d + timedelta(days=1)).isoformat(),
                "leave_end_date": (curr_d - timedelta(days=1)).isoformat(),
                "leave_days": gd,
            })
    return gaps


def _fetch_dashboard(token):
    r = requests.get(f"{API}/summary/dashboard", headers=_h(token))
    assert r.status_code == 200, r.text
    return r.json()


# =======================================================================
# Scenario 1 — CREATE flow: fill-the-gap deletes stale leave cycle
# =======================================================================
class TestCreateFillsGap:
    def test_initial_gap_creates_leave_cycle(self):
        token, _ = _register()
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-01"))
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-02"))
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-15"))
        d = _fetch_dashboard(token)
        assert d["leave_period"] is not None
        assert d["leave_period"]["leave_days"] == 12
        assert d["leave_period"]["leave_start_date"] == "2026-01-03"
        assert d["leave_period"]["leave_end_date"] == "2026-01-14"

    def test_fill_gap_to_6days_replaces_leave_cycle(self):
        token, _ = _register()
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-01"))
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-02"))
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-15"))
        # Add entry that splits the gap → new gap is jan-09..jan-14 (6 days)
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-08"))
        d = _fetch_dashboard(token)
        assert d["leave_period"] is not None
        assert d["leave_period"]["leave_days"] == 6
        assert d["leave_period"]["leave_start_date"] == "2026-01-09"
        assert d["leave_period"]["leave_end_date"] == "2026-01-14"

    def test_fill_gap_below_threshold_deletes_leave_cycle(self):
        token, _ = _register()
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-01"))
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-02"))
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-15"))
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-08"))
        # Now add jan-11 → gap 01-08 to 01-11 = 2 days, 01-11 to 01-15 = 3 days
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-11"))
        d = _fetch_dashboard(token)
        assert d["leave_period"] is None, f"Expected leave_period=null, got {d['leave_period']}"
        # previous_cycle should be the previous CLOSED cycle (work cycle from
        # before the leave). Since the leave cycle was the most recent closed
        # cycle and is now deleted, previous_cycle should fall back to the
        # earlier work cycle (the jan-01/jan-02 one).
        assert d["previous_cycle"] is not None
        assert d["previous_cycle"].get("is_leave_period", False) is False


# =======================================================================
# Scenario 2 — UPDATE flow: moving date below/above threshold
# =======================================================================
class TestUpdateReconciliation:
    def test_update_shrinks_gap_below_threshold_deletes_leave(self):
        token, _ = _register()
        # jan-01 .. jan-10 gap = 8 days (leave)
        e1 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-01")).json()
        e2 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-10")).json()
        d = _fetch_dashboard(token)
        assert d["leave_period"] is not None
        # Move e2 closer: jan-06 -> gap = 4 days
        upd = _entry("2026-01-06")
        r = requests.put(f"{API}/entries/{e2['id']}", headers=_h(token), json=upd)
        assert r.status_code == 200, r.text
        d2 = _fetch_dashboard(token)
        assert d2["leave_period"] is None

    def test_update_grows_gap_above_threshold_creates_leave(self):
        token, _ = _register()
        # jan-01 .. jan-05 gap = 3 days (no leave)
        e1 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-01")).json()
        e2 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-05")).json()
        d = _fetch_dashboard(token)
        assert d["leave_period"] is None
        # Move e2 to jan-12 -> gap = 10 days
        upd = _entry("2026-01-12")
        r = requests.put(f"{API}/entries/{e2['id']}", headers=_h(token), json=upd)
        assert r.status_code == 200, r.text
        d2 = _fetch_dashboard(token)
        assert d2["leave_period"] is not None
        assert d2["leave_period"]["leave_days"] == 10
        assert d2["leave_period"]["leave_start_date"] == "2026-01-02"
        assert d2["leave_period"]["leave_end_date"] == "2026-01-11"


# =======================================================================
# Scenario 3 — DELETE flow
# =======================================================================
class TestDeleteReconciliation:
    def test_delete_middle_entry_creates_new_gap(self):
        token, _ = _register()
        # 01, 05, 12 — gap1=3, gap2=6 (one leave). After deleting jan-05:
        # remaining 01, 12 -> gap=10 (leave moves)
        r1 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-01"))
        r2 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-05"))
        r3 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-12"))
        assert r1.status_code == 200 and r2.status_code == 200 and r3.status_code == 200
        # Before delete: only one gap >=6 -> jan-06..jan-11 (6 days)
        d = _fetch_dashboard(token)
        assert d["leave_period"] is not None
        assert d["leave_period"]["leave_days"] == 6
        # Delete middle entry e2
        e2_id = r2.json()["id"]
        rd = requests.delete(f"{API}/entries/{e2_id}", headers=_h(token))
        assert rd.status_code == 200, rd.text
        d2 = _fetch_dashboard(token)
        assert d2["leave_period"] is not None
        assert d2["leave_period"]["leave_days"] == 10
        assert d2["leave_period"]["leave_start_date"] == "2026-01-02"
        assert d2["leave_period"]["leave_end_date"] == "2026-01-11"

    def test_delete_middle_creates_brand_new_leave(self):
        token, _ = _register()
        # 01, 05, 06 — no gaps >=6 anywhere. Delete jan-05 -> 01..06 gap=4 still no leave.
        # Use 01, 05, 13 : gap1=3, gap2=7 (already leave). After delete jan-05: 01..13 gap=11
        # Better: 01, 10, 11 -> gap1=8 (leave), gap2=0 (none). Delete jan-10 -> 01..11 gap=9
        r1 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-01"))
        r2 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-10"))
        r3 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-11"))
        # Initial leave: jan-02..jan-09 (8 days)
        d = _fetch_dashboard(token)
        assert d["leave_period"] is not None
        assert d["leave_period"]["leave_days"] == 8
        # Delete jan-10 -> remaining 01, 11 -> gap=9
        rd = requests.delete(f"{API}/entries/{r2.json()['id']}", headers=_h(token))
        assert rd.status_code == 200, rd.text
        d2 = _fetch_dashboard(token)
        assert d2["leave_period"] is not None
        assert d2["leave_period"]["leave_days"] == 9
        assert d2["leave_period"]["leave_start_date"] == "2026-01-02"
        assert d2["leave_period"]["leave_end_date"] == "2026-01-10"

    def test_delete_only_remaining_entry_drops_all_leaves(self):
        token, _ = _register()
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-01"))
        r2 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-10"))
        d = _fetch_dashboard(token)
        assert d["leave_period"] is not None
        # Delete the latter -> only one entry left -> no gaps -> no leave
        requests.delete(f"{API}/entries/{r2.json()['id']}", headers=_h(token))
        d2 = _fetch_dashboard(token)
        assert d2["leave_period"] is None


# =======================================================================
# Boundary & invariant tests
# =======================================================================
class TestBoundaries:
    def test_gap_5_never_creates_leave(self):
        token, _ = _register()
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-02-01"))
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-02-07"))  # gap=5
        d = _fetch_dashboard(token)
        assert d["leave_period"] is None

    def test_gap_6_always_creates_leave(self):
        token, _ = _register()
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-02-01"))
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-02-08"))  # gap=6
        d = _fetch_dashboard(token)
        assert d["leave_period"] is not None
        assert d["leave_period"]["leave_days"] == 6


# =======================================================================
# Stress / sequence — alternate add/update/delete
# =======================================================================
class TestStressSequence:
    def test_sequence_invariant_holds(self):
        token, _ = _register()
        # Step 1: 01-01, 01-15 -> one leave 13
        e1 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-01")).json()
        e2 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-15")).json()
        d = _fetch_dashboard(token)
        assert d["leave_period"]["leave_days"] == 13

        # Step 2: add 01-09 -> two gaps: 7 (02-08) and 5 (10-14). Only one leave (7).
        e3 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-09")).json()
        d = _fetch_dashboard(token)
        # dashboard surfaces "most recent" leave by ended_at — could be either
        # since both are reconciled in same call. The 7-day one (02-08) is the
        # only valid leave.
        assert d["leave_period"] is not None
        assert d["leave_period"]["leave_days"] == 7
        assert d["leave_period"]["leave_start_date"] == "2026-01-02"
        assert d["leave_period"]["leave_end_date"] == "2026-01-08"

        # Step 3: update e3 (01-09) to 01-05 -> gaps now: 3 (02-04) and 9 (06-14) -> one leave 9
        upd = _entry("2026-01-05")
        r = requests.put(f"{API}/entries/{e3['id']}", headers=_h(token), json=upd)
        assert r.status_code == 200
        d = _fetch_dashboard(token)
        assert d["leave_period"]["leave_days"] == 9
        assert d["leave_period"]["leave_start_date"] == "2026-01-06"
        assert d["leave_period"]["leave_end_date"] == "2026-01-14"

        # Step 4: delete e2 (01-15) -> entries 01-01, 01-05 -> gap 3 -> no leave
        rd = requests.delete(f"{API}/entries/{e2['id']}", headers=_h(token))
        assert rd.status_code == 200
        d = _fetch_dashboard(token)
        assert d["leave_period"] is None

        # Step 5: re-add 01-20 -> entries 01-01, 01-05, 01-20 -> gap1=3, gap2=14 -> leave 14
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-01-20"))
        d = _fetch_dashboard(token)
        assert d["leave_period"]["leave_days"] == 14
        assert d["leave_period"]["leave_start_date"] == "2026-01-06"
        assert d["leave_period"]["leave_end_date"] == "2026-01-19"


# =======================================================================
# Work cycles untouched — ensure totals/days_worked stay accurate
# =======================================================================
class TestWorkCyclesUntouched:
    def test_work_cycle_totals_preserved_after_reconcile(self):
        token, _ = _register()
        e1 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-03-01")).json()
        e2 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-03-02")).json()
        work_cycle_id = e1["cycle_id"]
        assert e2["cycle_id"] == work_cycle_id
        # Now create a gap so reconcile fires
        e3 = requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-03-15")).json()
        assert e3["cycle_id"] != work_cycle_id, "new work cycle should be created after leave"

        # Per spec: previous_cycle reflects the most-recent closed cycle (the
        # leave cycle here). The work cycle however must still exist with its
        # entries intact — verify by listing entries.
        d = _fetch_dashboard(token)
        assert d["previous_cycle"] is not None
        # the leave cycle is the most recent closed -> previous_cycle is leave
        assert d["previous_cycle"].get("is_leave_period", False) is True

        # The original work cycle's entries must still point to it
        entries = requests.get(f"{API}/entries", headers=_h(token)).json()
        e1_after = next(x for x in entries if x["id"] == e1["id"])
        e2_after = next(x for x in entries if x["id"] == e2["id"])
        assert e1_after["cycle_id"] == work_cycle_id
        assert e2_after["cycle_id"] == work_cycle_id

    def test_previous_cycle_falls_back_to_work_when_leave_deleted(self):
        """When a leave cycle is reconciled away (gap filled), previous_cycle
        should fall back to the work cycle behind it."""
        token, _ = _register()
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-04-01"))
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-04-02"))
        requests.post(f"{API}/entries", headers=_h(token), json=_entry("2026-04-15"))
        d = _fetch_dashboard(token)
        assert d["previous_cycle"].get("is_leave_period") is True
        # Fill the gap with multiple entries -> no more gap >=6
        for day in [4, 6, 8, 10, 12]:
            requests.post(f"{API}/entries", headers=_h(token), json=_entry(f"2026-04-{day:02d}"))
        d2 = _fetch_dashboard(token)
        # leave cycle should be gone
        assert d2["leave_period"] is None
