"""Tests for the strict per-cycle 6-working-day cap (iteration 12).

Spec under test:
- A non-leave cycle MUST contain at most MAX_DAYS_PER_CYCLE (=6) entries.
- The 7th sequential POST /api/entries on the same cycle MUST return HTTP 400
  with detail = {code: 'cycle_max_days_reached', message: <french str>, max_days: 6}.
- The system MUST NOT auto-split / auto-create a new cycle. The user must
  explicitly call /api/cycles/start-new or /api/cycles/confirm-reduced, then retry.
- Leave-gap detection (>=6 inactive days) runs FIRST and closes the cycle, so an
  entry after a long absence still goes through (lands in a fresh cycle, days=1).
- PUT/DELETE do NOT increase entry count and must remain unaffected by the cap.
- GET /api/summary/dashboard exposes cycle.days_worked_max = 6 when a cycle is
  open, and the field is absent (cycle == None) when there is no open cycle.
"""
import os
import uuid
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://logbook-driver.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

MAX_DAYS = 6


# ---------- helpers ----------
def _register():
    email = f"TEST_cap_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": "Passw0rd!", "name": "Cap Test"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    return data["token"], data["user"]["id"], email


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _entry(d, start="08:00", end="16:00"):
    return {
        "date": d,
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


def _days(start_iso: str, n: int):
    """Return n consecutive YYYY-MM-DD strings starting at start_iso (gap=1 day)."""
    base = date.fromisoformat(start_iso)
    return [(base + timedelta(days=i)).isoformat() for i in range(n)]


def _post_entry(token, d):
    return requests.post(f"{API}/entries", headers=_h(token), json=_entry(d))


# =====================================================================
# 1. CAP ENFORCEMENT — six OK, seventh blocked with structured detail
# =====================================================================
class TestCapEnforcement:
    def test_six_sequential_entries_succeed(self):
        token, _, _ = _register()
        for d in _days("2025-02-03", MAX_DAYS):  # Mon..Sat
            r = _post_entry(token, d)
            assert r.status_code == 200, f"{d} failed: {r.status_code} {r.text}"
        # current cycle must hold exactly 6 entries
        dash = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert dash["cycle"] is not None
        assert dash["cycle"]["days_worked"] == MAX_DAYS
        assert dash["cycle"]["days_worked_max"] == MAX_DAYS

    def test_seventh_sequential_entry_returns_structured_400(self):
        token, _, _ = _register()
        days = _days("2025-02-03", MAX_DAYS + 1)  # 7 consecutive days
        for d in days[:MAX_DAYS]:
            assert _post_entry(token, d).status_code == 200
        r = _post_entry(token, days[MAX_DAYS])
        assert r.status_code == 400, r.text
        body = r.json()
        # FastAPI puts our structured payload under "detail"
        detail = body.get("detail")
        assert isinstance(detail, dict), f"detail must be a dict, got: {type(detail).__name__} -> {detail!r}"
        assert detail.get("code") == "cycle_max_days_reached"
        assert detail.get("max_days") == MAX_DAYS
        msg = detail.get("message", "")
        assert isinstance(msg, str) and len(msg) > 0
        # message must be French (heuristic: contains accented FR keywords)
        lower = msg.lower()
        assert any(k in lower for k in ("cycle", "journées", "nouveau")), f"non-french message: {msg!r}"

    def test_blocked_entry_not_persisted(self):
        """Blocked 7th entry must not create an entry document nor bump cycle counters."""
        token, _, _ = _register()
        days = _days("2025-02-03", MAX_DAYS + 1)
        for d in days[:MAX_DAYS]:
            assert _post_entry(token, d).status_code == 200
        r = _post_entry(token, days[MAX_DAYS])
        assert r.status_code == 400
        # Entry list still has exactly 6 entries
        listing = requests.get(f"{API}/entries", headers=_h(token)).json()
        assert len(listing) == MAX_DAYS
        # No entry for the blocked date
        assert all(e["date"] != days[MAX_DAYS] for e in listing)
        # Cycle counters unchanged
        dash = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert dash["cycle"]["days_worked"] == MAX_DAYS


# =====================================================================
# 2. MANUAL RECOVERY — start-new / confirm-reduced unblocks
# =====================================================================
class TestManualRecovery:
    def test_start_new_then_retry_succeeds_in_fresh_cycle(self):
        token, _, _ = _register()
        # 6 entries Feb 03..Feb 08 (each ending 16:00). Last entry ends Feb 08 16:00 UTC.
        days = _days("2025-02-03", MAX_DAYS)
        for d in days:
            assert _post_entry(token, d).status_code == 200
        original_cycle = requests.get(f"{API}/cycles/current", headers=_h(token)).json()
        assert original_cycle is not None
        original_cycle_id = original_cycle["id"]

        # 7th blocked at Feb 10 13:00 (45h after Feb 08 16:00)
        next_date, next_start = "2025-02-10", "13:00"
        # Try posting first → blocked by cap
        blocked = requests.post(
            f"{API}/entries", headers=_h(token),
            json=_entry(next_date, start=next_start),
        )
        assert blocked.status_code == 400
        assert blocked.json()["detail"]["code"] == "cycle_max_days_reached"

        # Start-new with the 45h-gap payload
        s = requests.post(
            f"{API}/cycles/start-new", headers=_h(token),
            json={"date": next_date, "start_time": next_start},
        )
        assert s.status_code == 200, s.text
        assert s.json()["closed_cycle_id"] == original_cycle_id

        # Retry — must now succeed in fresh cycle
        r2 = requests.post(
            f"{API}/entries", headers=_h(token),
            json=_entry(next_date, start=next_start),
        )
        assert r2.status_code == 200, r2.text

        # Dashboard: cycle.days_worked=1, previous_cycle.days_worked=6
        dash = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert dash["cycle"]["id"] != original_cycle_id
        assert dash["cycle"]["days_worked"] == 1
        assert dash["cycle"]["days_worked_max"] == MAX_DAYS
        assert dash["previous_cycle"] is not None
        assert dash["previous_cycle"]["id"] == original_cycle_id
        assert dash["previous_cycle"]["days_worked"] == MAX_DAYS
        assert dash["previous_cycle"].get("is_reduced_weekly_rest") in (False, None)

    def test_confirm_reduced_then_retry_marks_cycle_reduced(self):
        token, _, _ = _register()
        # 6 entries Feb 03..Feb 08 (each ending 16:00).
        for d in _days("2025-02-03", MAX_DAYS):
            assert _post_entry(token, d).status_code == 200
        original_cycle_id = requests.get(f"{API}/cycles/current", headers=_h(token)).json()["id"]

        # 24h after Feb 08 16:00 = Feb 09 16:00
        next_date, next_start = "2025-02-09", "16:00"

        # Blocked
        blocked = requests.post(
            f"{API}/entries", headers=_h(token),
            json=_entry(next_date, start=next_start),
        )
        assert blocked.status_code == 400

        # confirm-reduced with reduced-rest payload
        s = requests.post(
            f"{API}/cycles/confirm-reduced", headers=_h(token),
            json={"date": next_date, "start_time": next_start},
        )
        assert s.status_code == 200, s.text
        assert s.json()["closed_cycle_id"] == original_cycle_id

        # Retry — succeeds
        r2 = requests.post(
            f"{API}/entries", headers=_h(token),
            json=_entry(next_date, start=next_start),
        )
        assert r2.status_code == 200, r2.text

        dash = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert dash["cycle"]["days_worked"] == 1
        assert dash["previous_cycle"]["id"] == original_cycle_id
        assert dash["previous_cycle"]["is_reduced_weekly_rest"] is True


# =====================================================================
# 3. DASHBOARD — days_worked_max field surfacing
# =====================================================================
class TestDashboardDaysWorkedMax:
    def test_days_worked_max_present_when_cycle_open(self):
        token, _, _ = _register()
        assert _post_entry(token, "2025-03-03").status_code == 200
        dash = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert dash["cycle"] is not None
        assert dash["cycle"]["days_worked_max"] == MAX_DAYS

    def test_days_worked_max_absent_when_cycle_null(self):
        token, _, _ = _register()
        dash = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert dash["cycle"] is None
        # days_worked_max is only inside cycle dict — and cycle is None.
        # Spec: "null/no field when cycle is null". A null cycle implicitly
        # carries no max — verify it's not leaked anywhere else.
        assert "days_worked_max" not in dash


# =====================================================================
# 4. LEAVE-GAP INTERACTION — leave detection runs first, bypassing the cap
# =====================================================================
class TestLeaveGapBypassesCap:
    def test_six_entries_then_6day_gap_succeeds_in_fresh_cycle(self):
        token, _, _ = _register()
        # 6 consecutive entries Feb 3..Feb 8
        for d in _days("2025-02-03", MAX_DAYS):
            assert _post_entry(token, d).status_code == 200
        # Last entry date = 2025-02-08. Add an entry 6 calendar days after the
        # last working day -> Feb 15 (gap from Feb 09 to Feb 14 inclusive = 6
        # inactive days, triggers leave cycle).
        gap_entry = "2025-02-15"
        r = _post_entry(token, gap_entry)
        assert r.status_code == 200, f"leave-gap path should bypass cap. got {r.status_code} {r.text}"
        dash = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert dash["cycle"] is not None
        assert dash["cycle"]["days_worked"] == 1
        # A leave-period cycle should be exposed
        assert dash["leave_period"] is not None
        assert dash["leave_period"]["leave_days"] >= 6

    def test_gap_exactly_5_days_still_blocked(self):
        """Boundary: gap=5 (<LEAVE_THRESHOLD) does NOT close cycle, cap fires."""
        token, _, _ = _register()
        for d in _days("2025-02-03", MAX_DAYS):  # last entry Feb 8
            assert _post_entry(token, d).status_code == 200
        # gap of 5 inactive days = Feb 9..Feb 13 -> next entry Feb 14
        r = _post_entry(token, "2025-02-14")
        assert r.status_code == 400, r.text
        assert r.json()["detail"]["code"] == "cycle_max_days_reached"


# =====================================================================
# 5. PUT / DELETE — unaffected by the cap (count unchanged / decreased)
# =====================================================================
class TestPutDeleteUnaffected:
    def test_put_on_6entry_cycle_is_allowed(self):
        token, _, _ = _register()
        ids = []
        for d in _days("2025-02-03", MAX_DAYS):
            r = _post_entry(token, d)
            assert r.status_code == 200
            ids.append(r.json()["id"])
        # PUT the 3rd entry — changing times only, same date (no count change)
        target_id = ids[2]
        payload = _entry("2025-02-05", start="07:30", end="15:30")
        u = requests.put(f"{API}/entries/{target_id}", headers=_h(token), json=payload)
        assert u.status_code == 200, u.text
        body = u.json()
        assert body["start_time"] == "07:30"
        assert body["end_time"] == "15:30"
        # GET to verify persistence
        g = requests.get(f"{API}/entries/{target_id}", headers=_h(token))
        assert g.status_code == 200
        assert g.json()["start_time"] == "07:30"
        # Cycle still has exactly 6 entries
        dash = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert dash["cycle"]["days_worked"] == MAX_DAYS

    def test_delete_then_add_succeeds(self):
        token, _, _ = _register()
        ids = []
        for d in _days("2025-02-03", MAX_DAYS):
            r = _post_entry(token, d)
            assert r.status_code == 200
            ids.append(r.json()["id"])
        # 7th blocked
        days7 = (date.fromisoformat("2025-02-03") + timedelta(days=MAX_DAYS)).isoformat()
        assert _post_entry(token, days7).status_code == 400

        # Delete the LAST entry (Feb 8) — keeps cycle alive at 5 entries
        delete_id = ids[-1]
        d = requests.delete(f"{API}/entries/{delete_id}", headers=_h(token))
        assert d.status_code == 200, d.text
        dash = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert dash["cycle"] is not None, "deleting last entry of a 6-entry cycle should NOT delete the cycle"
        assert dash["cycle"]["days_worked"] == MAX_DAYS - 1

        # Now adding the previously blocked date succeeds (cap re-evaluated)
        r2 = _post_entry(token, days7)
        assert r2.status_code == 200, r2.text
        dash2 = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert dash2["cycle"]["days_worked"] == MAX_DAYS


# =====================================================================
# 6. NEGATIVE — repeated 7th attempts still blocked until manual action
# =====================================================================
class TestRepeatedBlockingIsIdempotent:
    def test_multiple_blocked_attempts_dont_corrupt_cycle(self):
        token, _, _ = _register()
        days = _days("2025-02-03", MAX_DAYS + 1)
        for d in days[:MAX_DAYS]:
            assert _post_entry(token, d).status_code == 200
        # Try the 7th THREE times — same response each time, no leak
        for _ in range(3):
            r = _post_entry(token, days[MAX_DAYS])
            assert r.status_code == 400
            assert r.json()["detail"]["code"] == "cycle_max_days_reached"
        dash = requests.get(f"{API}/summary/dashboard", headers=_h(token)).json()
        assert dash["cycle"]["days_worked"] == MAX_DAYS
        # No new cycle silently created
        listing = requests.get(f"{API}/entries", headers=_h(token)).json()
        assert len(listing) == MAX_DAYS
