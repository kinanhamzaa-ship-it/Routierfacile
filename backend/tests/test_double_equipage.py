"""
Iteration 8 — double_equipage is now informational only.
It is stored on the entry for traceability but does NOT relax the strict
EU 561/2006 + Code du travail break thresholds (45min total, 30min segment,
4h30 max consecutive). Tests verify:
- double_equipage flag is persisted (default False, accepts True)
- break_rule_status is identical regardless of double_equipage
- aggregates (amplitude/working/driving/rest) and cycle counters are unaffected
"""
import os
import uuid
import pytest
import requests


def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
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
    email = f"TEST_codrv_{uuid.uuid4().hex[:8]}@example.com"
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
    from datetime import date, timedelta
    y, m, d = [int(x) for x in base.split("-")]
    return (date(y, m, d) + timedelta(days=i)).isoformat()


# Schema acceptance
def test_dailyentry_accepts_double_equipage_default_false(headers):
    p = _make_payload(False, [120], [45])
    p["date"] = _next_day("2026-02-15", 0)
    p.pop("double_equipage")
    r = requests.post(f"{API}/entries", json=p, headers=headers, timeout=20)
    assert r.status_code in (200, 201), r.text
    assert r.json().get("double_equipage") is False


# Solo: 4h+4h with 30min break -> violation (max_consec 480>270)
def test_single_driver_240_240_with_30_violation(headers):
    p = _make_payload(False, [240, 240], [30])
    p["date"] = _next_day("2026-02-15", 1)
    body = _post(headers, p)
    assert body["break_rule_status"] == "violation"
    assert body["max_consecutive_driving_minutes"] == 480
    assert body["double_equipage"] is False


# Double équipage same inputs -> SAME result (violation) — no algorithmic effect
def test_codriver_240_240_with_30_still_violation(headers):
    p = _make_payload(True, [240, 240], [30])
    p["date"] = _next_day("2026-02-15", 2)
    body = _post(headers, p)
    assert body["break_rule_status"] == "violation"
    assert body["max_consecutive_driving_minutes"] == 480
    assert body["double_equipage"] is True


# Both modes: only 20min break -> violation
def test_codriver_240_240_with_20_violation(headers):
    p = _make_payload(True, [240, 240], [20])
    p["date"] = _next_day("2026-02-15", 3)
    body = _post(headers, p)
    assert body["break_rule_status"] == "violation"
    assert body["max_consecutive_driving_minutes"] == 480


# 4h+4h with 45 (split via [45] qualifies first 240, second 240 unbroken=240 max)
def test_codriver_240_240_with_45_ok(headers):
    p = _make_payload(True, [240, 240], [45])
    p["date"] = _next_day("2026-02-15", 4)
    body = _post(headers, p)
    assert body["break_rule_status"] == "ok"
    assert body["max_consecutive_driving_minutes"] == 240


# PUT toggle does NOT change break_rule_status (no algorithmic effect)
def test_put_toggle_does_not_change_break_rule(headers):
    p = _make_payload(False, [240, 240], [30])
    p["date"] = _next_day("2026-02-15", 5)
    created = _post(headers, p)
    eid = created["id"]
    assert created["break_rule_status"] == "violation"

    p["double_equipage"] = True
    r = requests.put(f"{API}/entries/{eid}", json=p, headers=headers, timeout=20)
    assert r.status_code in (200, 201), r.text
    updated = r.json()
    assert updated["double_equipage"] is True
    # Strict logic: status remains violation regardless of toggle
    assert updated["break_rule_status"] == "violation"
    assert updated["max_consecutive_driving_minutes"] == 480

    g = requests.get(f"{API}/entries/{eid}", headers=headers, timeout=20)
    assert g.status_code == 200
    fetched = g.json()
    assert fetched["double_equipage"] is True
    assert fetched["break_rule_status"] == "violation"


# Aggregates unaffected
def test_double_equipage_does_not_change_time_aggregates(headers):
    p_off = _make_payload(False, [240, 240], [30])
    p_off["date"] = _next_day("2026-02-15", 6)
    off = _post(headers, p_off)

    p_on = _make_payload(True, [240, 240], [30])
    p_on["date"] = _next_day("2026-02-15", 7)
    on = _post(headers, p_on)

    for k in ("amplitude_minutes", "total_working_minutes",
              "total_driving_minutes", "total_rest_minutes",
              "break_rule_status", "max_consecutive_driving_minutes"):
        assert off[k] == on[k], f"{k} differs: {off[k]} vs {on[k]}"
    assert on["amplitude_minutes"] == 960
    assert on["total_driving_minutes"] == 480
    assert on["total_rest_minutes"] == 30
    assert on["total_working_minutes"] == 930


# Cycle counters unaffected
def test_double_equipage_does_not_affect_cycle_counters():
    h, _ = _register()
    p1 = _make_payload(False, [240, 240], [30])
    p1["date"] = "2026-03-02"
    _post(h, p1)
    s1 = requests.get(f"{API}/summary/dashboard", headers=h, timeout=20).json()
    cyc1 = s1.get("cycle", {})

    p2 = _make_payload(True, [240, 240], [30])
    p2["date"] = "2026-03-03"
    _post(h, p2)
    s2 = requests.get(f"{API}/summary/dashboard", headers=h, timeout=20).json()
    cyc2 = s2.get("cycle", {})

    assert cyc2.get("total_driving_minutes", 0) == cyc1.get("total_driving_minutes", 0) + 480
    assert cyc2.get("reduced_rest_used", 0) == cyc1.get("reduced_rest_used", 0)
    assert cyc2.get("extensions_used", 0) == cyc1.get("extensions_used", 0)
