"""
Iteration 7 — Double équipage (co-driver) toggle.
Tests that double_equipage=True relaxes the 4h30/45min break rule:
- a break >=30min and <45min must NOT be a violation
- breaks <30min still trigger violation
- the toggle ONLY affects break_rule_status / max_consecutive_driving_minutes
  and does NOT change amplitude / worked / driving / rest / cycle counters.
"""
import os
import uuid
import time
import pytest
import requests

def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        # Fallback: read frontend/.env (kept inside repo)
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", ".env")
        try:
            with open(env_path) as fh:
                for line in fh:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.strip().split("=", 1)[1]
                        break
        except OSError:
            pass
    if not url:
        raise RuntimeError("REACT_APP_BACKEND_URL not set")
    return url.rstrip("/")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"


def _register():
    suffix = uuid.uuid4().hex[:8]
    email = f"TEST_codrv_{suffix}@example.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": "pass1234", "name": "TEST CoDriver"
    }, timeout=20)
    assert r.status_code in (200, 201), r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, email


@pytest.fixture(scope="module")
def headers():
    h, _ = _register()
    return h


def _make_payload(double_equipage, segments, breaks, date=None):
    # amplitude must cover working time. Use big window 06:00-22:00 (16h).
    return {
        "date": date or "2026-02-15",
        "start_time": "06:00",
        "end_time": "22:00",
        "driving_segments": segments,
        "rest_breaks": breaks,
        "departure": "Paris",
        "arrival": "Lyon",
        "notes": "TEST double_equipage",
        "decoucher": False,
        "meal_status": "yes",
        "double_equipage": double_equipage,
    }


def _post(headers, payload):
    r = requests.post(f"{API}/entries", json=payload, headers=headers, timeout=20)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _next_day(base, i):
    # base 2026-02-15 + i days
    from datetime import date, timedelta
    y, m, d = [int(x) for x in base.split("-")]
    return (date(y, m, d) + timedelta(days=i)).isoformat()


# ------- Schema / acceptance of new field -------
def test_dailyentry_accepts_double_equipage_default_false(headers):
    p = _make_payload(False, [120], [])
    p["date"] = _next_day("2026-02-15", 0)
    p.pop("double_equipage")  # field omitted should still work (default False)
    r = requests.post(f"{API}/entries", json=p, headers=headers, timeout=20)
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert body.get("double_equipage") is False


# ------- Single driver: 4h+4h with 30min break -> violation -------
def test_single_driver_240_240_with_30_violation(headers):
    p = _make_payload(False, [240, 240], [30])
    p["date"] = _next_day("2026-02-15", 1)
    body = _post(headers, p)
    assert body["break_rule_status"] == "violation"
    assert body["max_consecutive_driving_minutes"] == 480
    assert body["double_equipage"] is False


# ------- Double équipage: 4h+4h with 30min break -> OK (relaxed) -------
def test_codriver_240_240_with_30_ok(headers):
    p = _make_payload(True, [240, 240], [30])
    p["date"] = _next_day("2026-02-15", 2)
    body = _post(headers, p)
    assert body["break_rule_status"] == "ok"
    # 30min break resets accumulator -> max becomes 240
    assert body["max_consecutive_driving_minutes"] == 240
    assert body["double_equipage"] is True


# ------- Double équipage: 4h+4h with only 20min break -> still violation -------
def test_codriver_240_240_with_20_violation(headers):
    p = _make_payload(True, [240, 240], [20])
    p["date"] = _next_day("2026-02-15", 3)
    body = _post(headers, p)
    assert body["break_rule_status"] == "violation"
    assert body["max_consecutive_driving_minutes"] == 480


# ------- Double équipage: 4h+4h with 45min break -> OK (45 always qualifies) -------
def test_codriver_240_240_with_45_ok(headers):
    p = _make_payload(True, [240, 240], [45])
    p["date"] = _next_day("2026-02-15", 4)
    body = _post(headers, p)
    assert body["break_rule_status"] == "ok"
    assert body["max_consecutive_driving_minutes"] == 240


# ------- PUT recomputes break_rule_status when toggling -------
def test_put_toggle_recomputes_break_rule(headers):
    p = _make_payload(False, [240, 240], [30])
    p["date"] = _next_day("2026-02-15", 5)
    created = _post(headers, p)
    eid = created["id"]
    assert created["break_rule_status"] == "violation"

    # Toggle to co-driver
    p["double_equipage"] = True
    r = requests.put(f"{API}/entries/{eid}", json=p, headers=headers, timeout=20)
    assert r.status_code in (200, 201), r.text
    updated = r.json()
    assert updated["double_equipage"] is True
    assert updated["break_rule_status"] == "ok"
    assert updated["max_consecutive_driving_minutes"] == 240

    # GET to confirm persistence
    g = requests.get(f"{API}/entries/{eid}", headers=headers, timeout=20)
    assert g.status_code == 200
    fetched = g.json()
    assert fetched["double_equipage"] is True
    assert fetched["break_rule_status"] == "ok"

    # Toggle back -> violation again
    p["double_equipage"] = False
    r2 = requests.put(f"{API}/entries/{eid}", json=p, headers=headers, timeout=20)
    assert r2.status_code in (200, 201)
    again = r2.json()
    assert again["double_equipage"] is False
    assert again["break_rule_status"] == "violation"
    assert again["max_consecutive_driving_minutes"] == 480


# ------- double_equipage ONLY affects break_rule, not amplitude/working/driving/rest -------
def test_double_equipage_does_not_change_time_aggregates(headers):
    p_off = _make_payload(False, [240, 240], [30])
    p_off["date"] = _next_day("2026-02-15", 6)
    off = _post(headers, p_off)

    p_on = _make_payload(True, [240, 240], [30])
    p_on["date"] = _next_day("2026-02-15", 7)
    on = _post(headers, p_on)

    for k in ("amplitude_minutes", "total_working_minutes",
              "total_driving_minutes", "total_rest_minutes"):
        assert off[k] == on[k], f"{k} differs: {off[k]} vs {on[k]}"
    # amplitude 06:00-22:00 = 16h = 960
    assert on["amplitude_minutes"] == 960
    assert on["total_driving_minutes"] == 480
    assert on["total_rest_minutes"] == 30
    assert on["total_working_minutes"] == 930


# ------- Cycle counters are not impacted by the toggle -------
def test_double_equipage_does_not_affect_cycle_counters():
    # Fresh user so cycle counters are clean
    h, _ = _register()

    # Day 1 single driver
    p1 = _make_payload(False, [240, 240], [30])
    p1["date"] = "2026-03-02"  # a Monday
    _post(h, p1)
    s1 = requests.get(f"{API}/summary/dashboard", headers=h, timeout=20).json()
    cyc1 = s1.get("cycle", {})

    # Day 2 same shape but co-driver
    p2 = _make_payload(True, [240, 240], [30])
    p2["date"] = "2026-03-03"
    _post(h, p2)
    s2 = requests.get(f"{API}/summary/dashboard", headers=h, timeout=20).json()
    cyc2 = s2.get("cycle", {})

    # Driving total should add up (480 + 480 = 960), regardless of toggle
    assert cyc2.get("total_driving_minutes", 0) == cyc1.get("total_driving_minutes", 0) + 480
    # Extensions/reduced_rest counters should not be incremented by the co-driver toggle
    assert cyc2.get("reduced_rest_used", 0) == cyc1.get("reduced_rest_used", 0)
    assert cyc2.get("extensions_used", 0) == cyc1.get("extensions_used", 0)
