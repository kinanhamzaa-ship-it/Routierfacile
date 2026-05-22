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
from collections import defaultdict


# ============================================================
# Setup
# ============================================================
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="Routier Facile API")
api_router = APIRouter(prefix="/api")

JWT_ALGORITHM = "HS256"


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


# ============================================================
# Password & JWT helpers
# ============================================================
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


# ============================================================
# Models
# ============================================================
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
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    driving_segments: List[int] = Field(default_factory=list)  # minutes
    rest_breaks: List[int] = Field(default_factory=list)  # minutes
    departure: Optional[str] = ""
    arrival: Optional[str] = ""
    notes: Optional[str] = ""
    decoucher: bool = False
    meal_status: MealStatus = "unsure"


class DailyEntryOut(DailyEntryIn):
    id: str
    user_id: str
    created_at: str
    updated_at: str
    # computed
    total_driving_minutes: int
    total_rest_minutes: int
    total_working_minutes: int
    amplitude_minutes: int


# ============================================================
# Time computations
# ============================================================
def parse_hhmm_to_minutes(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def compute_amplitude(start: str, end: str) -> int:
    s = parse_hhmm_to_minutes(start)
    e = parse_hhmm_to_minutes(end)
    if e < s:
        e += 24 * 60  # overnight
    return e - s


def enrich_entry(doc: dict) -> dict:
    driving = sum(int(x) for x in doc.get("driving_segments", []))
    rest = sum(int(x) for x in doc.get("rest_breaks", []))
    amp = compute_amplitude(doc["start_time"], doc["end_time"])
    working = max(amp - rest, 0)
    doc["total_driving_minutes"] = driving
    doc["total_rest_minutes"] = rest
    doc["total_working_minutes"] = working
    doc["amplitude_minutes"] = amp
    return doc


# ============================================================
# Auth dependency
# ============================================================
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
# Auth endpoints
# ============================================================
@api_router.post("/auth/register", response_model=AuthResponse)
async def register(payload: RegisterIn, response: Response):
    email = payload.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name or email.split("@")[0],
        "role": "driver",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(doc)
    token = create_access_token(user_id, email)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=7 * 24 * 3600, path="/")
    return {"user": {"id": user_id, "email": email, "name": doc["name"], "role": "driver"}, "token": token}


@api_router.post("/auth/login", response_model=AuthResponse)
async def login(payload: LoginIn, response: Response):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    token = create_access_token(user["id"], email)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=7 * 24 * 3600, path="/")
    return {"user": {"id": user["id"], "email": email, "name": user.get("name"), "role": user.get("role", "driver")}, "token": token}


@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api_router.get("/auth/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return {"id": user["id"], "email": user["email"], "name": user.get("name"), "role": user.get("role", "driver")}


# ============================================================
# Daily entries
# ============================================================
@api_router.post("/entries", response_model=DailyEntryOut)
async def create_entry(payload: DailyEntryIn, user: dict = Depends(get_current_user)):
    existing = await db.entries.find_one({"user_id": user["id"], "date": payload.date})
    if existing:
        raise HTTPException(status_code=400, detail="Une entrée existe déjà pour cette date. Modifiez-la.")
    now = datetime.now(timezone.utc).isoformat()
    doc = payload.model_dump()
    doc.update({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "created_at": now,
        "updated_at": now,
    })
    enrich_entry(doc)
    to_insert = {k: v for k, v in doc.items()}
    await db.entries.insert_one(to_insert)
    return {k: v for k, v in doc.items() if k != "_id"}


@api_router.get("/entries", response_model=List[DailyEntryOut])
async def list_entries(
    user: dict = Depends(get_current_user),
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 200,
):
    q = {"user_id": user["id"]}
    if start or end:
        d = {}
        if start:
            d["$gte"] = start
        if end:
            d["$lte"] = end
        q["date"] = d
    cursor = db.entries.find(q, {"_id": 0}).sort("date", -1).limit(limit)
    items = await cursor.to_list(length=limit)
    for it in items:
        enrich_entry(it)
    return items


@api_router.get("/entries/{entry_id}", response_model=DailyEntryOut)
async def get_entry(entry_id: str, user: dict = Depends(get_current_user)):
    doc = await db.entries.find_one({"id": entry_id, "user_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Entrée introuvable")
    enrich_entry(doc)
    return doc


@api_router.put("/entries/{entry_id}", response_model=DailyEntryOut)
async def update_entry(entry_id: str, payload: DailyEntryIn, user: dict = Depends(get_current_user)):
    existing = await db.entries.find_one({"id": entry_id, "user_id": user["id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Entrée introuvable")
    update = payload.model_dump()
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.entries.update_one({"id": entry_id, "user_id": user["id"]}, {"$set": update})
    merged = {**existing, **update}
    enrich_entry(merged)
    return merged


@api_router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: str, user: dict = Depends(get_current_user)):
    res = await db.entries.delete_one({"id": entry_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entrée introuvable")
    return {"ok": True}


# ============================================================
# Summary endpoints
# ============================================================
def iso_week_range(target: date_cls):
    # Monday as first day
    monday = target - timedelta(days=target.weekday())
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


@api_router.get("/summary/week")
async def week_summary(date: Optional[str] = None, user: dict = Depends(get_current_user)):
    target = date_cls.fromisoformat(date) if date else datetime.now(timezone.utc).date()
    start, end = iso_week_range(target)
    cursor = db.entries.find({"user_id": user["id"], "date": {"$gte": start, "$lte": end}}, {"_id": 0})
    entries = await cursor.to_list(length=10)
    for e in entries:
        enrich_entry(e)
    total_driving = sum(e["total_driving_minutes"] for e in entries)
    total_working = sum(e["total_working_minutes"] for e in entries)
    total_rest = sum(e["total_rest_minutes"] for e in entries)
    decoucher_count = sum(1 for e in entries if e.get("decoucher"))
    weekly_limit = 56 * 60  # minutes
    remaining = max(weekly_limit - total_driving, 0)
    if total_driving >= weekly_limit:
        status = "red"
    elif total_driving >= weekly_limit * 0.85:
        status = "orange"
    else:
        status = "green"
    return {
        "week_start": start,
        "week_end": end,
        "total_driving_minutes": total_driving,
        "total_working_minutes": total_working,
        "total_rest_minutes": total_rest,
        "decoucher_count": decoucher_count,
        "days_worked": len(entries),
        "weekly_limit_minutes": weekly_limit,
        "remaining_minutes": remaining,
        "status": status,
        "entries": entries,
    }


@api_router.get("/summary/month")
async def month_summary(year: int, month: int, user: dict = Depends(get_current_user)):
    start = date_cls(year, month, 1).isoformat()
    if month == 12:
        end = date_cls(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date_cls(year, month + 1, 1) - timedelta(days=1)
    end_iso = end.isoformat()
    cursor = db.entries.find({"user_id": user["id"], "date": {"$gte": start, "$lte": end_iso}}, {"_id": 0}).sort("date", 1)
    entries = await cursor.to_list(length=500)
    for e in entries:
        enrich_entry(e)
    total_driving = sum(e["total_driving_minutes"] for e in entries)
    total_working = sum(e["total_working_minutes"] for e in entries)
    total_rest = sum(e["total_rest_minutes"] for e in entries)
    decoucher_count = sum(1 for e in entries if e.get("decoucher"))
    meal_counts = {"yes": 0, "no": 0, "unsure": 0}
    for e in entries:
        meal_counts[e.get("meal_status", "unsure")] = meal_counts.get(e.get("meal_status", "unsure"), 0) + 1
    return {
        "year": year,
        "month": month,
        "total_driving_minutes": total_driving,
        "total_working_minutes": total_working,
        "total_rest_minutes": total_rest,
        "decoucher_count": decoucher_count,
        "working_days": len(entries),
        "meal_counts": meal_counts,
        "entries": entries,
    }


@api_router.get("/summary/dashboard")
async def dashboard_summary(user: dict = Depends(get_current_user)):
    today = datetime.now(timezone.utc).date()
    week = await week_summary(date=today.isoformat(), user=user)
    month = await month_summary(year=today.year, month=today.month, user=user)
    # Compare today's rest to yesterday: if today's working > 13h amp warning
    last_entries_cursor = db.entries.find({"user_id": user["id"]}, {"_id": 0}).sort("date", -1).limit(2)
    last = await last_entries_cursor.to_list(length=2)
    daily_rest_status = "green"
    if len(last) >= 1:
        e = last[0]
        enrich_entry(e)
        if e["amplitude_minutes"] > 15 * 60:
            daily_rest_status = "red"
        elif e["amplitude_minutes"] > 13 * 60:
            daily_rest_status = "orange"
    return {
        "week": week,
        "month": {
            "year": month["year"],
            "month": month["month"],
            "total_driving_minutes": month["total_driving_minutes"],
            "decoucher_count": month["decoucher_count"],
            "working_days": month["working_days"],
            "meal_counts": month["meal_counts"],
        },
        "daily_rest_status": daily_rest_status,
    }


# ============================================================
# Bootstrap
# ============================================================
@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.entries.create_index([("user_id", 1), ("date", -1)])
    # Seed admin
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@routier-facile.fr")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin123!")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "Admin",
            "role": "admin",
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
