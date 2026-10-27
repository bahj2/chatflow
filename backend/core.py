"""Shared app state: env, database, auth dependencies, business settings and rate limiting."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os  # noqa: E402
import time  # noqa: E402
import logging  # noqa: E402
from collections import deque  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from typing import List, Literal  # noqa: E402

import bcrypt  # noqa: E402
import jwt  # noqa: E402
from fastapi import HTTPException, Request, Depends  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import billing as B  # noqa: E402


client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]
EMERGENT_LLM_KEY = os.environ['EMERGENT_LLM_KEY']
JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALG = "HS256"

MODELS = {
    "luna": ("openai", "gpt-6-luna"),
    "claude": ("anthropic", "claude-sonnet-4-5-20250929"),
    "gemini": ("gemini", "gemini-3-flash-preview"),
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

class FAQ(BaseModel):
    q: str
    a: str


class QuickReply(BaseModel):
    label: str
    text: str


DEFAULT_QUICK = [
    {"label": "Prices", "text": "Our prices start from $__. Tell me what you're interested in and I'll send exact details!"},
    {"label": "Address", "text": "You can find us at: __ (street, city). See you soon!"},
    {"label": "Opening hours", "text": "We're open Mon–Sat, 9:00–18:00. Sunday closed."},
]


class Settings(BaseModel):
    business_name: str = "My Business"
    business_type: str = "generic"
    business_info: str = ""
    assistant_name: str = Field("", max_length=40)
    greeting: str = Field("", max_length=500)
    faqs: List[FAQ] = []
    tone: str = "friendly"
    language: str = "auto"
    model: str = "luna"
    auto_reply: bool = True
    telegram_token: str = ""
    fb_page_token: str = ""
    fb_page_id: str = ""
    fb_verify_token: str = ""
    fb_app_secret: str = ""
    quick_replies: List[QuickReply] = Field(default_factory=lambda: [QuickReply(**q) for q in DEFAULT_QUICK])
    allowed_emails: List[str] = []
    voice_replies: bool = True
    voice: Literal["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"] = "nova"
    seller_voice_media_id: str = ""
    seller_voice_text: str = ""
    bakong_account_id: str = Field("", max_length=60)
    bakong_merchant_name: str = Field("", max_length=25)
    bakong_city: str = Field("Phnom Penh", max_length=15)
    khqr_token: str = Field("", max_length=300)

def hash_pw(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_pw(p, h):
    return bcrypt.checkpw(p.encode(), h.encode())


async def current_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(auth[7:], JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return user

EMAIL_RE = r"[^@\s]+@[^@\s]+\.[^@\s]+"

async def superadmin(user=Depends(current_user)):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Platform admin only")
    return user

async def get_settings(bid: str) -> Settings:
    doc = await db.settings.find_one({"business_id": bid}, {"_id": 0, "business_id": 0})
    return Settings(**(doc or {}))

async def platform_settings():
    """The superadmin's own business: its Bakong payment details receive the shops' subscription payments."""
    admin = await db.users.find_one({"role": "superadmin"}, {"_id": 0, "business_id": 1})
    return await get_settings(admin["business_id"]) if admin and admin.get("business_id") else None

async def require_pro(bid: str):
    if not (await B.sub_status(db, bid))["pro"]:
        raise HTTPException(402, B.PRO_ONLY)

RATE = {}


PROXY_HOPS = 2  # Cloudflare + load balancer append after the real client IP


def client_ip(request: Request) -> str:
    parts = [p.strip() for p in (request.headers.get("x-forwarded-for") or "").split(",") if p.strip()]
    if len(parts) > PROXY_HOPS:
        return parts[-(PROXY_HOPS + 1)]
    return parts[0] if parts else request.client.host


def rate_ok(rules) -> bool:
    now = time.time()
    if len(RATE) > 20000:
        for k in [k for k, q in RATE.items() if not q or q[-1] < now - 3600]:
            RATE.pop(k, None)
    queues = []
    for key, limit, window in rules:
        q = RATE.setdefault(key, deque())
        while q and q[0] < now - window:
            q.popleft()
        if len(q) >= limit:
            return False
        queues.append(q)
    for q in queues:
        q.append(now)
    return True
