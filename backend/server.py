from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta, date as date_cls
from typing import List, Optional, Literal
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict


# ============================================================
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="Routier Facile API")
api_router = APIRouter(prefix="/api")

JWT_ALGORITHM = "HS256"
DAILY_DRIVING_EXTENSION_MIN = 9 * 60  # > 9h triggers extension counter
DAILY_DRIVING_EXTENSION_MAX = 10 * 60
WEEKLY_REST_FULL = 45 * 60  # >= 45h => weekly rest
WEEKLY_REST_MIN = 24 * 60   # 24-45h => reduced weekly rest candidate
DAILY_REST_OK = 11 * 60
DAILY_REST_REDUCED = 9 * 60
MAX_CONSECUTIVE_DRIVING = 4 * 60 + 30  # 4h30 before mandatory break
MIN_QUALIFYING_BREAK = 45  # minutes total to reset driving counter
MIN_SECOND_SPLIT_BREAK = 30  # at least one break of 30+ min within split
LEAVE_THRESHOLD_DAYS = 6  # >=6 consecutive inactive days create a leave-period cycle


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str, email: str) -> str:
    return jwt.encode(
        {"sub": user_id, "email": email, "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "access"},
        get_jwt_secret(), algorithm=JWT_ALGORITHM,
    )


# ============================================================
# Models
class UserOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: Optional[str] = None
    role: str = "driver"


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: Optional[str] = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user: UserOut
    token: str


MealStatus = Literal["yes", "no", "unsure"]


class DailyEntryIn(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    driving_segments: List[int] = Field(default_factory=list)
    rest_breaks: List[int] = Field(default_factory=list)
    departure: Optional[str] = ""
    arrival: Optional[str] = ""
    notes: Optional[str] = ""
    decoucher: bool = False
    meal_status: MealStatus = "unsure"
    double_equipage: bool = False


class DetectIn(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")


# ============================================================
# Time helpers
def parse_hhmm_to_minutes(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def compute_amplitude(start: str, end: str) -> int:
    s = parse_hhmm_to_minutes(start)
    e = parse_hhmm_to_minutes(end)
    if e < s:
        e += 24 * 60
    return e - s


def to_dt(date_str: str, hhmm: str) -> datetime:
    y, m, d = [int(x) for x in date_str.split("-")]
    h, mi = [int(x) for x in hhmm.split(":")]
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


def end_dt(entry: dict) -> datetime:
    """Returns the actual end datetime accounting for overnight shifts."""
    start = to_dt(entry["date"], entry["start_time"])
    end = to_dt(entry["date"], entry["end_time"])
    if end < start:
        end = end + timedelta(days=1)
    return end


def compute_break_rule(driving_segments, rest_breaks):
    """
    Strict break validation (EU 561/2006 + Code du travail safeguard):
    For any working day with driving > 0, BOTH conditions must hold:
      1. Max consecutive driving never exceeds 4h30 (using cumulative reset when a
         qualifying 45min pause has been taken — supports the 15+30 split with
         the 30min segment present).
      2. Total break duration must be >= 45 min AND include at least one
         segment >= 30 min.
    Days with no driving are always 'ok'. double_equipage is stored on the entry
    for traceability but does NOT relax these thresholds — the 30min Code du
    travail break is informational, not a 4h30 reset trigger.
    """
    acc_drive = 0
    acc_break = 0
    has_30_in_window = False
    max_acc = 0
    for i, seg in enumerate(driving_segments):
        acc_drive += int(seg)
        max_acc = max(max_acc, acc_drive)
        if i < len(rest_breaks):
            b = int(rest_breaks[i])
            acc_break += b
            if b >= MIN_SECOND_SPLIT_BREAK:
                has_30_in_window = True
            if acc_break >= MIN_QUALIFYING_BREAK and has_30_in_window:
                acc_drive = 0
                acc_break = 0
                has_30_in_window = False

    total_driving = sum(int(x) for x in driving_segments)
    total_break = sum(int(x) for x in rest_breaks)
    has_30_overall = any(int(b) >= MIN_SECOND_SPLIT_BREAK for b in rest_breaks)

    violated = (
        max_acc > MAX_CONSECUTIVE_DRIVING
        or (total_driving > 0 and (total_break < MIN_QUALIFYING_BREAK or not has_30_overall))
    )
    status = "violation" if violated else "ok"
    return {"max_consecutive_driving_minutes": max_acc, "break_rule_status": status}


def enrich_entry(doc: dict) -> dict:
    driving = sum(int(x) for x in doc.get("driving_segments", []))
    rest = sum(int(x) for x in doc.get("rest_breaks", []))
    amp = compute_amplitude(doc["start_time"], doc["end_time"])
    working = max(amp - rest, 0)
    doc["total_driving_minutes"] = driving
    doc["total_rest_minutes"] = rest
    doc["total_working_minutes"] = working
    doc["amplitude_minutes"] = amp
    # daily_rest_status from already-stored daily_rest_minutes
    dr = doc.get("daily_rest_minutes")
    if dr is None:
        doc["daily_rest_status"] = None
    elif dr >= DAILY_REST_OK:
        doc["daily_rest_status"] = "ok"
    elif dr >= DAILY_REST_REDUCED:
        doc["daily_rest_status"] = "reduced"
    else:
        doc["daily_rest_status"] = "warning"
    # extension flag
    doc["is_driving_extension"] = DAILY_DRIVING_EXTENSION_MIN < driving <= DAILY_DRIVING_EXTENSION_MAX
    doc["is_legacy"] = doc.get("cycle_id") is None
    # 4h30 / 45min break rule. double_equipage is stored for traceability but does
    # NOT alter the 4h30 driving validation (45min relay required in both modes).
    br = compute_break_rule(doc.get("driving_segments", []), doc.get("rest_breaks", []))
    doc.update(br)
    return doc


# ============================================================
# Auth dep
async def get_current_user(request: Request) -> dict:
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Non authentifié")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expirée")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Jeton invalide")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    user.pop("password_hash", None)
    return user


# ============================================================
# Cycle helpers
async def get_current_cycle(user_id: str) -> Optional[dict]:
    """Read-only: return the current OPEN cycle or None. Never creates."""
    return await db.cycles.find_one(
        {"user_id": user_id, "ended_at": None}, {"_id": 0}
    )


async def get_or_create_cycle_for_entry(user_id: str) -> dict:
    """Used ONLY by create_entry: return current open cycle, creating one if
    none exists (an empty cycle must never appear without a same-call entry)."""
    cyc = await get_current_cycle(user_id)
    if cyc:
        return cyc
    new_cyc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "reduced_rest_used": 0,
        "extensions_used": 0,
        "break_violations_count": 0,
        "is_reduced_weekly_rest": False,  # set on the cycle that ENDS with a reduced rest
    }
    await db.cycles.insert_one(dict(new_cyc))
    return new_cyc


async def close_current_cycle(user_id: str, mark_reduced: bool = False) -> Optional[str]:
    """Close the current open cycle (sets ended_at) and optionally flag it as
    ending with a reduced weekly rest. Returns the closed cycle id, or None if
    no open cycle existed. Does NOT create a new cycle — that happens lazily on
    the next create_entry call."""
    now = datetime.now(timezone.utc).isoformat()
    update = {"ended_at": now}
    if mark_reduced:
        update["is_reduced_weekly_rest"] = True
    res = await db.cycles.find_one_and_update(
        {"user_id": user_id, "ended_at": None},
        {"$set": update},
        return_document=False,  # return doc before update; we just need its id
    )
    return res["id"] if res else None


async def detect_and_create_leave_cycle(user_id: str, new_entry_date: str) -> Optional[dict]:
    """If at least LEAVE_THRESHOLD_DAYS full inactive days separate the previous
    entry from the incoming entry, close the current open cycle and create an
    empty 'leave-period' cycle covering the entire absence. Returns the leave
    cycle if created, else None.

    Skipped entirely if the new entry is being back-dated (i.e. any existing
    entry has a later date) — leave detection must only fire on chronological
    additions."""
    later = await db.entries.find_one(
        {"user_id": user_id, "date": {"$gt": new_entry_date}}, {"_id": 0}
    )
    if later:
        return None
    prev = await db.entries.find_one(
        {"user_id": user_id, "date": {"$lt": new_entry_date}},
        {"_id": 0}, sort=[("date", -1)]
    )
    if not prev:
        return None
    py, pm, pd = [int(x) for x in prev["date"].split("-")]
    ny, nm, nd = [int(x) for x in new_entry_date.split("-")]
    prev_d = date_cls(py, pm, pd)
    new_d = date_cls(ny, nm, nd)
    gap_days = (new_d - prev_d).days - 1  # full inactive days between the two
    if gap_days < LEAVE_THRESHOLD_DAYS:
        return None
    # Close the work cycle that prev belongs to (if still open).
    await close_current_cycle(user_id, mark_reduced=False)
    leave_start = (prev_d + timedelta(days=1)).isoformat()
    leave_end = (new_d - timedelta(days=1)).isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()
    leave_cyc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "started_at": leave_start + "T00:00:00+00:00",
        # ended_at uses now_iso so the leave cycle sorts AFTER the work cycle
        # just closed above — making it the "most recent closed" reference.
        "ended_at": now_iso,
        "is_leave_period": True,
        "leave_days": gap_days,
        "leave_start_date": leave_start,
        "leave_end_date": leave_end,
        "is_reduced_weekly_rest": False,
        "reduced_rest_used": 0,
        "extensions_used": 0,
        "break_violations_count": 0,
        "total_driving_minutes": 0,
        "total_working_minutes": 0,
        "total_rest_minutes": 0,
        "days_worked": 0,
        "decoucher_count": 0,
    }
    await db.cycles.insert_one(dict(leave_cyc))
    leave_cyc.pop("_id", None)
    return leave_cyc


async def reconcile_leave_cycles(user_id: str):
    """Re-derive the user's leave-period cycles from the current entries.
    Leave cycles are a pure projection of gaps >= LEAVE_THRESHOLD_DAYS between
    consecutive entries:
      - any stored leave cycle whose covered range no longer matches a current
        gap is deleted;
      - any current gap without a matching leave cycle gets one created.
    Work (non-leave) cycles are NEVER touched here."""
    entries = await db.entries.find(
        {"user_id": user_id}, {"_id": 0, "date": 1}
    ).sort("date", 1).to_list(length=10000)

    valid_gaps = {}  # (leave_start_date, leave_end_date) -> leave_days
    for i in range(1, len(entries)):
        py, pm, pd = [int(x) for x in entries[i - 1]["date"].split("-")]
        cy, cm, cd = [int(x) for x in entries[i]["date"].split("-")]
        prev_d = date_cls(py, pm, pd)
        curr_d = date_cls(cy, cm, cd)
        gap_days = (curr_d - prev_d).days - 1
        if gap_days >= LEAVE_THRESHOLD_DAYS:
            start = (prev_d + timedelta(days=1)).isoformat()
            end = (curr_d - timedelta(days=1)).isoformat()
            valid_gaps[(start, end)] = gap_days

    existing = await db.cycles.find(
        {"user_id": user_id, "is_leave_period": True}, {"_id": 0}
    ).to_list(length=200)
    existing_keys = set()
    for lc in existing:
        key = (lc.get("leave_start_date"), lc.get("leave_end_date"))
        if key in valid_gaps:
            existing_keys.add(key)
        else:
            await db.cycles.delete_one({"id": lc["id"]})

    now_iso = datetime.now(timezone.utc).isoformat()
    for (start, end), days in valid_gaps.items():
        if (start, end) in existing_keys:
            continue
        leave_cyc = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "started_at": start + "T00:00:00+00:00",
            "ended_at": now_iso,
            "is_leave_period": True,
            "leave_days": days,
            "leave_start_date": start,
            "leave_end_date": end,
            "is_reduced_weekly_rest": False,
            "reduced_rest_used": 0,
            "extensions_used": 0,
            "break_violations_count": 0,
            "total_driving_minutes": 0,
            "total_working_minutes": 0,
            "total_rest_minutes": 0,
            "days_worked": 0,
            "decoucher_count": 0,
        }
        await db.cycles.insert_one(dict(leave_cyc))




async def recompute_cycle_counters(cycle_id: str):
    """Recompute counters and snapshot totals from all entries in cycle."""
    cursor = db.entries.find({"cycle_id": cycle_id}, {"_id": 0})
    entries = await cursor.to_list(length=200)
    reduced = 0
    ext = 0
    violations = 0
    total_driving = 0
    total_working = 0
    total_rest = 0
    decoucher_count = 0
    for e in entries:
        enrich_entry(e)
        total_driving += e["total_driving_minutes"]
        total_working += e["total_working_minutes"]
        total_rest += e["total_rest_minutes"]
        if e.get("decoucher"):
            decoucher_count += 1
        if e.get("daily_rest_status") == "reduced":
            reduced += 1
        if e.get("is_driving_extension"):
            ext += 1
        if e.get("break_rule_status") == "violation":
            violations += 1
    await db.cycles.update_one(
        {"id": cycle_id},
        {"$set": {
            "reduced_rest_used": reduced,
            "extensions_used": ext,
            "break_violations_count": violations,
            "total_driving_minutes": total_driving,
            "total_working_minutes": total_working,
            "total_rest_minutes": total_rest,
            "days_worked": len(entries),
            "decoucher_count": decoucher_count,
            "last_recomputed_at": datetime.now(timezone.utc).isoformat(),
        }}
    )


# ============================================================
# Auth endpoints
@api_router.post("/auth/register", response_model=AuthResponse)
async def register(payload: RegisterIn, response: Response):
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
    uid = str(uuid.uuid4())
    await db.users.insert_one({
        "id": uid, "email": email, "password_hash": hash_password(payload.password),
        "name": payload.name or email.split("@")[0], "role": "driver",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    token = create_access_token(uid, email)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=7*24*3600, path="/")
    return {"user": {"id": uid, "email": email, "name": payload.name or email.split("@")[0], "role": "driver"}, "token": token}


@api_router.post("/auth/login", response_model=AuthResponse)
async def login(payload: LoginIn, response: Response):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    token = create_access_token(user["id"], email)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=7*24*3600, path="/")
    return {"user": {"id": user["id"], "email": email, "name": user.get("name"), "role": user.get("role", "driver")}, "token": token}


@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api_router.get("/auth/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return {"id": user["id"], "email": user["email"], "name": user.get("name"), "role": user.get("role", "driver")}


# ============================================================
# Detection
@api_router.post("/cycles/detect-rest")
async def detect_rest(payload: DetectIn, user: dict = Depends(get_current_user)):
    """Given a new start datetime, look at previous entry's end and return detection signal."""
    prev = await db.entries.find_one(
        {"user_id": user["id"], "date": {"$lt": payload.date}},
        {"_id": 0}, sort=[("date", -1)]
    )
    if not prev:
        return {"daily_rest_minutes": None, "detection": None}
    prev_end = end_dt(prev)
    new_start = to_dt(payload.date, payload.start_time)
    rest_minutes = int((new_start - prev_end).total_seconds() // 60)
    if rest_minutes < 0:
        rest_minutes = 0
    detection = None
    if rest_minutes >= WEEKLY_REST_FULL:
        detection = "weekly_rest_full"
    elif rest_minutes >= WEEKLY_REST_MIN:
        detection = "weekly_rest_reduced"
    return {"daily_rest_minutes": rest_minutes, "detection": detection}


# ============================================================
# Cycle endpoints
@api_router.get("/cycles/current")
async def current_cycle(user: dict = Depends(get_current_user)):
    cyc = await get_current_cycle(user["id"])
    return cyc  # may be None


@api_router.post("/cycles/start-new")
async def start_new_cycle(user: dict = Depends(get_current_user)):
    closed_id = await close_current_cycle(user["id"], mark_reduced=False)
    return {"closed_cycle_id": closed_id}


@api_router.post("/cycles/confirm-reduced")
async def confirm_reduced(user: dict = Depends(get_current_user)):
    closed_id = await close_current_cycle(user["id"], mark_reduced=True)
    return {"closed_cycle_id": closed_id}


# ============================================================
# Entries
@api_router.post("/entries")
async def create_entry(payload: DailyEntryIn, user: dict = Depends(get_current_user)):
    if await db.entries.find_one({"user_id": user["id"], "date": payload.date}):
        raise HTTPException(status_code=400, detail="Une entrée existe déjà pour cette date. Modifiez-la.")
    # Compute daily rest
    prev = await db.entries.find_one(
        {"user_id": user["id"], "date": {"$lt": payload.date}},
        {"_id": 0}, sort=[("date", -1)]
    )
    daily_rest = None
    if prev:
        prev_end = end_dt(prev)
        new_start = to_dt(payload.date, payload.start_time)
        daily_rest = max(int((new_start - prev_end).total_seconds() // 60), 0)
    # If a long absence preceded this entry, close the previous cycle and stamp
    # an empty leave-period cycle covering it before opening the new one.
    await detect_and_create_leave_cycle(user["id"], payload.date)
    cyc = await get_or_create_cycle_for_entry(user["id"])
    now = datetime.now(timezone.utc).isoformat()
    doc = payload.model_dump()
    doc.update({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "cycle_id": cyc["id"],
        "daily_rest_minutes": daily_rest,
        "created_at": now,
        "updated_at": now,
    })
    enrich_entry(doc)
    await db.entries.insert_one(dict(doc))
    await recompute_cycle_counters(cyc["id"])
    await reconcile_leave_cycles(user["id"])
    return {k: v for k, v in doc.items() if k != "_id"}


@api_router.get("/entries")
async def list_entries(user: dict = Depends(get_current_user), start: Optional[str] = None, end: Optional[str] = None, limit: int = 200):
    q = {"user_id": user["id"]}
    if start or end:
        d = {}
        if start:
            d["$gte"] = start
        if end:
            d["$lte"] = end
        q["date"] = d
    items = await db.entries.find(q, {"_id": 0}).sort("date", -1).limit(limit).to_list(length=limit)
    for it in items:
        enrich_entry(it)
    return items


@api_router.get("/entries/{entry_id}")
async def get_entry(entry_id: str, user: dict = Depends(get_current_user)):
    doc = await db.entries.find_one({"id": entry_id, "user_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Entrée introuvable")
    enrich_entry(doc)
    return doc


@api_router.put("/entries/{entry_id}")
async def update_entry(entry_id: str, payload: DailyEntryIn, user: dict = Depends(get_current_user)):
    existing = await db.entries.find_one({"id": entry_id, "user_id": user["id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Entrée introuvable")
    # Recompute daily rest based on (possibly new) date/start
    prev = await db.entries.find_one(
        {"user_id": user["id"], "date": {"$lt": payload.date}, "id": {"$ne": entry_id}},
        {"_id": 0}, sort=[("date", -1)]
    )
    daily_rest = None
    if prev:
        prev_end = end_dt(prev)
        new_start = to_dt(payload.date, payload.start_time)
        daily_rest = max(int((new_start - prev_end).total_seconds() // 60), 0)
    update = payload.model_dump()
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    update["daily_rest_minutes"] = daily_rest
    await db.entries.update_one({"id": entry_id, "user_id": user["id"]}, {"$set": update})
    merged = {**existing, **update}
    enrich_entry(merged)
    if existing.get("cycle_id"):
        await recompute_cycle_counters(existing["cycle_id"])
    await reconcile_leave_cycles(user["id"])
    return merged


@api_router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: str, user: dict = Depends(get_current_user)):
    existing = await db.entries.find_one({"id": entry_id, "user_id": user["id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Entrée introuvable")
    await db.entries.delete_one({"id": entry_id, "user_id": user["id"]})
    reverted_to_cycle = None
    deleted_empty_cycle = False
    cycle_id = existing.get("cycle_id")
    if cycle_id:
        await recompute_cycle_counters(cycle_id)
        cyc = await db.cycles.find_one({"id": cycle_id})
        if cyc and cyc.get("ended_at") is None:
            remaining = await db.entries.count_documents(
                {"user_id": user["id"], "cycle_id": cycle_id}
            )
            if remaining == 0:
                # Empty cycles are never allowed: always delete.
                prev = await db.cycles.find_one(
                    {
                        "user_id": user["id"],
                        "id": {"$ne": cycle_id},
                        "ended_at": {"$ne": None},
                        "is_leave_period": {"$ne": True},
                    },
                    sort=[("ended_at", -1)],
                )
                await db.cycles.delete_one({"id": cycle_id})
                deleted_empty_cycle = True
                # If there's a previous closed cycle, reopen it so the driver
                # continues from where they were.
                if prev:
                    await db.cycles.update_one(
                        {"id": prev["id"]},
                        {"$set": {"ended_at": None, "is_reduced_weekly_rest": False}},
                    )
                    await recompute_cycle_counters(prev["id"])
                    reverted_to_cycle = prev["id"]
    await reconcile_leave_cycles(user["id"])
    return {
        "ok": True,
        "reverted_to_cycle": reverted_to_cycle,
        "deleted_empty_cycle": deleted_empty_cycle,
    }


# ============================================================
# Summaries
@api_router.get("/summary/dashboard")
async def dashboard_summary(user: dict = Depends(get_current_user)):
    cyc = await get_current_cycle(user["id"])
    # Entries in current open cycle (empty list if no cycle)
    if cyc:
        entries = await db.entries.find({"user_id": user["id"], "cycle_id": cyc["id"]}, {"_id": 0}).sort("date", -1).to_list(length=200)
    else:
        entries = []
    for e in entries:
        enrich_entry(e)
    total_driving = sum(e["total_driving_minutes"] for e in entries)
    total_working = sum(e["total_working_minutes"] for e in entries)
    total_rest = sum(e["total_rest_minutes"] for e in entries)
    decoucher_count_cycle = sum(1 for e in entries if e.get("decoucher"))
    days = len(entries)

    today_iso = datetime.now(timezone.utc).date().isoformat()
    today_entry = next((e for e in entries if e["date"] == today_iso), None)
    last_entry_cycle = entries[0] if entries else None

    # Latest entry across ALL entries (not just current cycle) — used by dashboard snapshot + daily rest tile
    latest_doc = await db.entries.find_one(
        {"user_id": user["id"]},
        {"_id": 0},
        sort=[("date", -1)]
    )
    if latest_doc:
        # Backfill daily_rest_minutes on the fly for legacy/older entries
        if latest_doc.get("daily_rest_minutes") is None:
            prev = await db.entries.find_one(
                {"user_id": user["id"], "date": {"$lt": latest_doc["date"]}},
                {"_id": 0}, sort=[("date", -1)]
            )
            if prev:
                latest_doc["daily_rest_minutes"] = max(
                    int((to_dt(latest_doc["date"], latest_doc["start_time"]) - end_dt(prev)).total_seconds() // 60),
                    0,
                )
        enrich_entry(latest_doc)

    # Previous closed cycle — for visibility/comparison at the start of new cycle.
    # The most recent closed cycle is used as-is. If it is a leave-period cycle,
    # its zero totals act as a reset point (showing 0h00 in the comparison table).
    prev_cycle_doc = await db.cycles.find_one(
        {"user_id": user["id"], "ended_at": {"$ne": None}},
        {"_id": 0},
        sort=[("ended_at", -1)],
    )
    previous_cycle = None
    if prev_cycle_doc:
        # Backfill snapshot if missing on old cycles
        if prev_cycle_doc.get("total_driving_minutes") is None:
            await recompute_cycle_counters(prev_cycle_doc["id"])
            prev_cycle_doc = await db.cycles.find_one({"id": prev_cycle_doc["id"]}, {"_id": 0})
        previous_cycle = {
            "id": prev_cycle_doc["id"],
            "started_at": prev_cycle_doc.get("started_at"),
            "ended_at": prev_cycle_doc.get("ended_at"),
            "is_reduced_weekly_rest": prev_cycle_doc.get("is_reduced_weekly_rest", False),
            "is_leave_period": prev_cycle_doc.get("is_leave_period", False),
            "leave_start_date": prev_cycle_doc.get("leave_start_date"),
            "leave_end_date": prev_cycle_doc.get("leave_end_date"),
            "leave_days": prev_cycle_doc.get("leave_days", 0),
            "total_driving_minutes": prev_cycle_doc.get("total_driving_minutes", 0),
            "total_working_minutes": prev_cycle_doc.get("total_working_minutes", 0),
            "total_rest_minutes": prev_cycle_doc.get("total_rest_minutes", 0),
            "days_worked": prev_cycle_doc.get("days_worked", 0),
            "decoucher_count": prev_cycle_doc.get("decoucher_count", 0),
            "reduced_rest_used": prev_cycle_doc.get("reduced_rest_used", 0),
            "extensions_used": prev_cycle_doc.get("extensions_used", 0),
            "break_violations_count": prev_cycle_doc.get("break_violations_count", 0),
        }

    # Latest leave-period cycle (informational gap marker between previous work
    # cycle and the current one). Surfaced only if it occurred AFTER the previous
    # work cycle's end — i.e. it sits between previous work cycle and current.
    leave_doc = await db.cycles.find_one(
        {"user_id": user["id"], "is_leave_period": True},
        {"_id": 0},
        sort=[("ended_at", -1)],
    )
    leave_period = None
    if leave_doc and (not prev_cycle_doc or leave_doc.get("ended_at", "") >= prev_cycle_doc.get("ended_at", "")):
        leave_period = {
            "id": leave_doc["id"],
            "leave_days": leave_doc.get("leave_days", 0),
            "leave_start_date": leave_doc.get("leave_start_date"),
            "leave_end_date": leave_doc.get("leave_end_date"),
            "ended_at": leave_doc.get("ended_at"),
        }

    # Month stats (calendar month, for meal counters)
    now = datetime.now(timezone.utc).date()
    m_start = now.replace(day=1).isoformat()
    if now.month == 12:
        m_end_d = date_cls(now.year + 1, 1, 1) - timedelta(days=1)
    else:
        m_end_d = date_cls(now.year, now.month + 1, 1) - timedelta(days=1)
    m_entries = await db.entries.find({"user_id": user["id"], "date": {"$gte": m_start, "$lte": m_end_d.isoformat()}}, {"_id": 0}).to_list(length=400)
    for e in m_entries:
        enrich_entry(e)
    meal_counts = {"yes": 0, "no": 0, "unsure": 0}
    decoucher_month = 0
    driving_month = 0
    for e in m_entries:
        meal_counts[e.get("meal_status", "unsure")] = meal_counts.get(e.get("meal_status", "unsure"), 0) + 1
        if e.get("decoucher"):
            decoucher_month += 1
        driving_month += e["total_driving_minutes"]

    return {
        "cycle": (
            {
                "id": cyc["id"],
                "started_at": cyc["started_at"],
                "is_reduced_weekly_rest": cyc.get("is_reduced_weekly_rest", False),
                "total_driving_minutes": total_driving,
                "total_working_minutes": total_working,
                "total_rest_minutes": total_rest,
                "days_worked": days,
                "decoucher_count": decoucher_count_cycle,
                "reduced_rest_used": cyc.get("reduced_rest_used", 0),
                "reduced_rest_max": 3,
                "extensions_used": cyc.get("extensions_used", 0),
                "extensions_max": 2,
                "break_violations_count": cyc.get("break_violations_count", 0),
            }
            if cyc
            else None
        ),
        "today": today_entry,
        "last_entry": last_entry_cycle,
        "latest_entry": latest_doc,
        "previous_cycle": previous_cycle,
        "leave_period": leave_period,
        "month": {
            "year": now.year,
            "month": now.month,
            "total_driving_minutes": driving_month,
            "working_days": len(m_entries),
            "decoucher_count": decoucher_month,
            "meal_counts": meal_counts,
        },
    }


@api_router.get("/summary/month")
async def month_summary(year: int, month: int, user: dict = Depends(get_current_user)):
    start = date_cls(year, month, 1).isoformat()
    end_d = date_cls(year + 1, 1, 1) - timedelta(days=1) if month == 12 else date_cls(year, month + 1, 1) - timedelta(days=1)
    entries = await db.entries.find({"user_id": user["id"], "date": {"$gte": start, "$lte": end_d.isoformat()}}, {"_id": 0}).sort("date", 1).to_list(length=500)
    for e in entries:
        enrich_entry(e)
    meal_counts = {"yes": 0, "no": 0, "unsure": 0}
    for e in entries:
        meal_counts[e.get("meal_status", "unsure")] = meal_counts.get(e.get("meal_status", "unsure"), 0) + 1
    return {
        "year": year, "month": month,
        "total_driving_minutes": sum(e["total_driving_minutes"] for e in entries),
        "total_working_minutes": sum(e["total_working_minutes"] for e in entries),
        "total_rest_minutes": sum(e["total_rest_minutes"] for e in entries),
        "decoucher_count": sum(1 for e in entries if e.get("decoucher")),
        "working_days": len(entries),
        "meal_counts": meal_counts,
        "entries": entries,
    }


# ============================================================
# Bootstrap
@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.entries.create_index([("user_id", 1), ("date", -1)])
    await db.cycles.create_index([("user_id", 1), ("ended_at", 1)])
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@routier-facile.fr")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin123!")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()), "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "Admin", "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


@api_router.get("/")
async def root():
    return {"app": "Routier Facile", "status": "ok"}


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
