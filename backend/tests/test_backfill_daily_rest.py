"""Direct DB test — backfill of daily_rest_minutes when latest entry is legacy
(cycle_id None, daily_rest_minutes None) but has a prior entry to compare against.
"""
import os, asyncio, uuid, pytest, requests
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')


@pytest.fixture(scope="module")
def db():
    return AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]


@pytest.fixture(scope="module")
def legacy_user(db):
    """Register a user, then seed 2 legacy entries directly in DB
    (cycle_id=None, daily_rest_minutes=None)."""
    email = f"TEST_bf_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/auth/register",
                      json={"email": email, "password": "Passw0rd!", "name": "Backfill"})
    assert r.status_code == 200
    token = r.json()["token"]
    uid = r.json()["user"]["id"]

    async def seed():
        now = datetime.now(timezone.utc).isoformat()
        for d, s, e in [("2025-12-01", "06:00", "18:00"), ("2025-12-02", "05:30", "15:00")]:
            await db.entries.insert_one({
                "id": str(uuid.uuid4()), "user_id": uid,
                "date": d, "start_time": s, "end_time": e,
                "driving_segments": [240, 180], "rest_breaks": [45],
                "departure": "", "arrival": "", "notes": "",
                "decoucher": False, "meal_status": "unsure",
                "cycle_id": None, "daily_rest_minutes": None,
                "created_at": now, "updated_at": now,
            })

    asyncio.get_event_loop().run_until_complete(seed())
    return {"email": email, "token": token, "id": uid}


def test_dashboard_backfills_daily_rest_for_legacy_latest(legacy_user):
    """The latest legacy entry (2025-12-02 05:30) should have daily_rest
    backfilled relative to previous (2025-12-01 ends 18:00) => 11h30 = 690min."""
    h = {"Authorization": f"Bearer {legacy_user['token']}"}
    r = requests.get(f"{BASE_URL}/api/summary/dashboard", headers=h)
    assert r.status_code == 200
    latest = r.json()["latest_entry"]
    assert latest is not None
    assert latest["date"] == "2025-12-02"
    assert latest["is_legacy"] is True
    assert latest["daily_rest_minutes"] == 690, f"expected backfilled 690, got {latest.get('daily_rest_minutes')}"
    assert latest["daily_rest_status"] == "ok"


def test_dashboard_legacy_first_entry_no_backfill(db):
    """A user with ONE legacy entry only — no prev => daily_rest stays None."""
    email = f"TEST_solo_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/auth/register",
                      json={"email": email, "password": "Passw0rd!", "name": "Solo"})
    token = r.json()["token"]
    uid = r.json()["user"]["id"]

    async def seed():
        await db.entries.insert_one({
            "id": str(uuid.uuid4()), "user_id": uid,
            "date": "2025-11-01", "start_time": "08:00", "end_time": "16:00",
            "driving_segments": [240], "rest_breaks": [],
            "departure": "", "arrival": "", "notes": "",
            "decoucher": False, "meal_status": "unsure",
            "cycle_id": None, "daily_rest_minutes": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    asyncio.get_event_loop().run_until_complete(seed())
    h = {"Authorization": f"Bearer {token}"}
    rd = requests.get(f"{BASE_URL}/api/summary/dashboard", headers=h)
    latest = rd.json()["latest_entry"]
    assert latest is not None
    assert latest["is_legacy"] is True
    assert latest["daily_rest_minutes"] is None
    assert latest.get("daily_rest_status") is None
