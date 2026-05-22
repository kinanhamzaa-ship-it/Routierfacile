"""
Iteration 8 — STRICT break validation regression suite.
For ANY day with driving > 0:
  - total break must be >= 45 min
  - at least one break segment must be >= 30 min
  - max consecutive driving must be <= 4h30 (cumulative reset only by a
    qualifying 45+min+30+segment pause)
double_equipage is stored on the entry for traceability but does NOT relax
any thresholds.
"""
import os
import uuid
import pytest
import requests


def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", ".env")
        with open(env_path) as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    url = line.strip().split("=", 1)[1]
                    break
    if not url:
        raise RuntimeError("REACT_APP_BACKEND_URL not set")
    return url.rstrip("/")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"


def _register():
    email = f"TEST_strict_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register",
                      json={"email": email, "password": "pass1234", "name": "TEST Strict"},
                      timeout=20)
    assert r.status_code in (200, 201), r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def headers():
    return _register()


def _next_day(base, i):
    from datetime import date, timedelta
    y, m, d = [int(x) for x in base.split("-")]
    return (date(y, m, d) + timedelta(days=i)).isoformat()


def _payload(segments, breaks, day_idx, double_equipage=False, start="06:00", end="22:00"):
    return {
        "date": _next_day("2026-05-01", day_idx),
        "start_time": start,
        "end_time": end,
        "driving_segments": segments,
        "rest_breaks": breaks,
        "departure": "A", "arrival": "B", "notes": "TEST strict",
        "decoucher": False, "meal_status": "unsure",
        "double_equipage": double_equipage,
    }


def _post(headers, payload):
    r = requests.post(f"{API}/entries", json=payload, headers=headers, timeout=20)
    assert r.status_code in (200, 201), r.text
    return r.json()


# ---------- Strict break rule scenarios (from review_request) ----------
class TestStrictBreakRule:
    def test_240_drive_20_break_violation(self, headers):
        """4h driving + 20min break => violation (total<45)."""
        b = _post(headers, _payload([240], [20], 0))
        assert b["break_rule_status"] == "violation"

    def test_240_drive_45_break_ok(self, headers):
        """4h driving + 45min single break => ok."""
        b = _post(headers, _payload([240], [45], 1))
        assert b["break_rule_status"] == "ok"

    def test_240_drive_30_15_break_ok(self, headers):
        """4h driving + split [30,15]=45 with 30+ segment => ok."""
        b = _post(headers, _payload([240], [30, 15], 2))
        assert b["break_rule_status"] == "ok"

    def test_120_drive_20_break_violation_strict(self, headers):
        """Low driving (2h) + 20min break => still violation (strict total>=45)."""
        b = _post(headers, _payload([120], [20], 3))
        assert b["break_rule_status"] == "violation"

    def test_no_driving_no_break_ok(self, headers):
        """No driving => always ok."""
        b = _post(headers, _payload([], [], 4))
        assert b["break_rule_status"] == "ok"

    def test_480_drive_60_break_violation_max_consecutive(self, headers):
        """480 single segment > 270 max consecutive => violation."""
        b = _post(headers, _payload([480], [60], 5))
        assert b["break_rule_status"] == "violation"
        assert b["max_consecutive_driving_minutes"] == 480

    def test_240_drive_60_break_ok(self, headers):
        """4h + 60min single break (60>=45 and 60>=30) => ok."""
        b = _post(headers, _payload([240], [60], 6))
        assert b["break_rule_status"] == "ok"

    def test_240_drive_three_15_breaks_violation(self, headers):
        """Edge: 4h + [15,15,15]=45 total but no individual >=30 => violation."""
        b = _post(headers, _payload([240], [15, 15, 15], 7))
        assert b["break_rule_status"] == "violation"


# ---------- double_equipage does NOT relax thresholds ----------
class TestDoubleEquipageNoEffect:
    @pytest.mark.parametrize("segs,brks,expected", [
        ([240], [20], "violation"),
        ([240], [45], "ok"),
        ([240], [30, 15], "ok"),
        ([240], [15, 15, 15], "violation"),
        ([240, 240], [30], "violation"),
        ([240, 240], [45], "ok"),  # 45min between segs resets accumulator, max=240
        ([270, 270], [30], "violation"),  # 30min<45 doesn't reset, max=540>270
    ])
    def test_same_result_both_modes(self, headers, segs, brks, expected):
        """double_equipage true/false must yield the same break_rule_status."""
        solo = _post(headers, _payload(segs, brks, 10 + hash((tuple(segs), tuple(brks))) % 30,
                                       double_equipage=False))
        co = _post(headers, _payload(segs, brks, 50 + hash((tuple(segs), tuple(brks))) % 30,
                                     double_equipage=True))
        assert solo["break_rule_status"] == expected, f"solo {segs}/{brks} expected {expected}"
        assert co["break_rule_status"] == expected, f"codriver {segs}/{brks} expected {expected}"
        assert solo["break_rule_status"] == co["break_rule_status"]
        # double_equipage flag persisted
        assert solo["double_equipage"] is False
        assert co["double_equipage"] is True
