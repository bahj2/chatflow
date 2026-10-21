from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import re
import json
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import bcrypt
import httpx
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, BackgroundTasks, Query, UploadFile, File, Form
from fastapi.responses import PlainTextResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError, OperationFailure
import asyncio
from fastapi.responses import Response
from collections import deque
import hashlib
import hmac
import time
from pydantic import BaseModel, Field
from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
import media as M

client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]
EMERGENT_LLM_KEY = os.environ['EMERGENT_LLM_KEY']
JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALG = "HS256"

MODELS = {
    "claude": ("anthropic", "claude-sonnet-4-5-20250929"),
    "gemini": ("gemini", "gemini-3-flash-preview"),
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
api = APIRouter(prefix="/api")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------- Models ----------
class LoginIn(BaseModel):
    email: str
    password: str


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
    faqs: List[FAQ] = []
    tone: str = "friendly"
    language: str = "auto"
    model: str = "claude"
    auto_reply: bool = True
    greeting: str = "Hi! How can I help you today?"
    telegram_token: str = ""
    fb_page_token: str = ""
    fb_verify_token: str = ""
    fb_app_secret: str = ""
    quick_replies: List[QuickReply] = Field(default_factory=lambda: [QuickReply(**q) for q in DEFAULT_QUICK])
    allowed_emails: List[str] = []
    voice_replies: bool = True
    voice: str = "nova"
    khmer_voice: str = "sreymom"
    voxcpm_url: str = ""
    voxcpm_key: str = ""
    voxcpm_for: str = "khmer"
    seller_voice_media_id: str = ""
    seller_voice_text: str = ""


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    price: str = Field(default="", max_length=40)
    description: str = Field(default="", max_length=1000)
    image_media_id: str = ""


class PublicChatIn(BaseModel):
    session_id: str = Field(max_length=100)
    text: str = Field(max_length=2000)
    name: Optional[str] = None


class ReplyIn(BaseModel):
    text: str


class ConvPatch(BaseModel):
    ai_enabled: Optional[bool] = None
    unread: Optional[int] = None


class TelegramConnectIn(BaseModel):
    base_url: str


class TestAIIn(BaseModel):
    text: str


# ---------- Auth ----------
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


@api.post("/auth/login")
async def login(body: LoginIn, request: Request):
    email = body.email.strip().lower()
    ident = f"{client_ip(request)}:{email}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("count", 0) >= 5 and datetime.fromisoformat(att["last"]) > datetime.now(timezone.utc) - timedelta(minutes=15):
        raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash") or not verify_pw(body.password, user["password_hash"]):
        await db.login_attempts.update_one({"identifier": ident}, {"$inc": {"count": 1}, "$set": {"last": now_iso()}}, upsert=True)
        raise HTTPException(401, "Invalid email or password")
    await db.login_attempts.delete_one({"identifier": ident})
    return await issue_token(user)


async def issue_token(user: dict) -> dict:
    token = jwt.encode({"sub": user["id"], "email": user["email"], "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "access"}, JWT_SECRET, algorithm=JWT_ALG)
    biz = await db.businesses.find_one({"id": user["business_id"]}, {"_id": 0, "name": 1})
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user.get("name"), "picture": user.get("picture"),
                                     "role": user.get("role"), "business_id": user["business_id"], "business_name": (biz or {}).get("name")}}


EMAIL_RE = r"[^@\s]+@[^@\s]+\.[^@\s]+"


async def create_business(name: str, owner_id: str) -> str:
    bid = str(uuid.uuid4())
    await db.businesses.insert_one({"id": bid, "name": name, "owner_id": owner_id, "created_at": now_iso()})
    await db.settings.insert_one({"business_id": bid, **Settings(business_name=name).model_dump()})
    return bid


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=128)
    business_name: str = Field(min_length=1, max_length=80)


@api.post("/auth/register")
async def register(body: RegisterIn, request: Request):
    email = body.email.strip().lower()
    if not re.fullmatch(EMAIL_RE, email):
        raise HTTPException(400, "Please enter a valid email")
    if not rate_ok([(f"reg:{client_ip(request)}", 10, 3600)]):
        raise HTTPException(429, "Too many sign-ups from this network. Try again later.")
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "An account with this email already exists. Please sign in.")
    uid = str(uuid.uuid4())
    bid = await create_business(body.business_name.strip(), uid)
    user = {"id": uid, "email": email, "name": body.business_name.strip(), "password_hash": hash_pw(body.password),
            "role": "owner", "business_id": bid, "created_at": now_iso()}
    await db.users.insert_one(dict(user))
    return await issue_token(user)


class GoogleIn(BaseModel):
    session_id: str


@api.post("/auth/google")
async def google_login(body: GoogleIn):
    try:
        async with httpx.AsyncClient(timeout=20) as h:
            r = await h.get("https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data", headers={"X-Session-ID": body.session_id})
        g = r.json() if r.status_code == 200 else {}
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, "Google sign-in is unavailable right now. Please try again.")
    if not g.get("email"):
        raise HTTPException(401, "Google sign-in failed. Please try again.")
    email = g["email"].strip().lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if user:
        await db.users.update_one({"email": email}, {"$set": {"picture": g.get("picture"), "name": user.get("name") or g.get("name")}})
        user["picture"] = g.get("picture")
    else:
        uid = str(uuid.uuid4())
        team = await db.settings.find_one({"allowed_emails": email}, {"_id": 0, "business_id": 1})
        if team:
            bid, role = team["business_id"], "member"
        else:
            bid, role = await create_business(f"{g.get('name') or email.split('@')[0]}'s business", uid), "owner"
        user = {"id": uid, "email": email, "name": g.get("name"), "picture": g.get("picture"), "role": role, "auth": "google",
                "business_id": bid, "created_at": now_iso()}
        await db.users.insert_one(dict(user))
    return await issue_token(user)


@api.get("/auth/me")
async def me(user=Depends(current_user)):
    biz = await db.businesses.find_one({"id": user["business_id"]}, {"_id": 0, "name": 1})
    return {**user, "business_name": (biz or {}).get("name")}


async def superadmin(user=Depends(current_user)):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Platform admin only")
    return user


@api.get("/admin/businesses")
async def admin_businesses(user=Depends(superadmin)):
    bizs = await db.businesses.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    convs = {d["_id"]: d["n"] async for d in db.conversations.aggregate([{"$group": {"_id": "$business_id", "n": {"$sum": 1}}}])}
    ai = {d["_id"]: d["n"] async for d in db.messages.aggregate([{"$match": {"role": "ai"}}, {"$group": {"_id": "$business_id", "n": {"$sum": 1}}}])}
    owners = {u["id"]: u["email"] async for u in db.users.find({"id": {"$in": [b["owner_id"] for b in bizs]}}, {"_id": 0, "id": 1, "email": 1})}
    tg = {d["business_id"] async for d in db.settings.find({"telegram_token": {"$ne": ""}}, {"_id": 0, "business_id": 1})}
    fb = {d["business_id"] async for d in db.settings.find({"fb_page_token": {"$ne": ""}}, {"_id": 0, "business_id": 1})}
    return [{**b, "owner_email": owners.get(b["owner_id"]), "conversations": convs.get(b["id"], 0), "ai_replies": ai.get(b["id"], 0),
             "telegram": b["id"] in tg, "messenger": b["id"] in fb} for b in bizs]


# ---------- Settings ----------
async def get_settings(bid: str) -> Settings:
    doc = await db.settings.find_one({"business_id": bid}, {"_id": 0, "business_id": 0})
    return Settings(**(doc or {}))


@api.get("/settings")
async def read_settings(user=Depends(current_user)):
    return (await get_settings(user["business_id"])).model_dump()


@api.put("/settings")
async def write_settings(body: Settings, user=Depends(current_user)):
    body.allowed_emails = sorted({e.strip().lower() for e in body.allowed_emails if re.fullmatch(EMAIL_RE, e.strip())})
    await db.settings.update_one({"business_id": user["business_id"]}, {"$set": body.model_dump()}, upsert=True)
    await db.businesses.update_one({"id": user["business_id"]}, {"$set": {"name": body.business_name}})
    return body.model_dump()


# ---------- AI ----------
TONES = {
    "friendly": "warm, friendly and upbeat",
    "professional": "polite, professional and precise",
    "direct": "short, direct and to the point",
    "witty": "light, witty and charming while staying helpful",
}


SHOW_TAG = re.compile(r"\[\[show:([^\]]*)\]\]", re.I)
ASK_PHOTO = re.compile(r"\s*(would|do|shall|can) (you|i) (like|want|show)[^.?!]*\b(see|photo|picture|image|look)[^.?!]*\?\s*$", re.I)


def catalog_text(products: list) -> str:
    if not products:
        return ""
    rows = "\n".join(f"{p['id'][:8]} | {p['name']} | {p.get('price') or '-'} | {(p.get('description') or '')[:160]}" for p in products)
    return ("\n\nPRODUCT CATALOG (ref | name | price | description):\n" + rows +
            "\n\nWhen the customer asks about products, prices or availability, or seeing a product would clearly help, "
            "mention the product name and price in your reply and END your reply with a tag like [[show:ref1,ref2]] "
            "listing up to 3 refs from the catalog that best match (only refs that exist). The product photos are sent automatically "
            "with your reply, so never ask whether they want to see a photo. Otherwise add no tag.")


def split_show(text: str, products: list) -> tuple:
    refs = [r.strip().lower() for m in SHOW_TAG.findall(text) for r in m.split(",") if r.strip()]
    clean = SHOW_TAG.sub("", text).strip()
    picked = [p for r in refs for p in products if p["id"].startswith(r)]
    seen = set()
    picked = [p for p in picked if not (p["id"] in seen or seen.add(p["id"]))][:3]
    if picked:
        clean = ASK_PHOTO.sub("", clean).strip()
    return clean, picked


async def load_products(bid: str) -> list:
    return await db.products.find({"business_id": bid, "is_deleted": False}, {"_id": 0}).sort("created_at", -1).to_list(300)


def system_prompt(s: Settings, products: Optional[list] = None) -> str:
    faqs = "\n".join(f"Q: {f.q}\nA: {f.a}" for f in s.faqs) or "(none)"
    lang = "Always reply in the same language the customer writes in." if s.language == "auto" else f"Always reply in {s.language}."
    return (
        f"You are the customer support assistant for '{s.business_name}' (type: {s.business_type}).\n"
        f"Business information:\n{s.business_info or '(not provided)'}\n\nFAQs:\n{faqs}\n\n"
        f"Style: {TONES.get(s.tone, TONES['friendly'])}. Keep replies short (1-3 sentences), clear and easy to read on a phone. "
        f"Understand what the customer really wants, answer it directly, and suggest a next step when helpful. {lang} "
        "Only use the business information and FAQs for facts like prices, hours or policies; if you don't know, say a team member will follow up. "
        "Never mention you are an AI model name. Plain text only, no markdown."
        + catalog_text(products or [])
    )


async def llm(s: Settings, system: str, text: str) -> str:
    provider, model = MODELS.get(s.model, MODELS["claude"])
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=str(uuid.uuid4()), system_message=system).with_model(provider, model)
    out = ""
    async for ev in chat.stream_message(UserMessage(text=text)):
        if isinstance(ev, TextDelta):
            out += ev.content
        elif isinstance(ev, StreamDone):
            break
    return out.strip()


async def transcript(conv_id: str, limit: int = 20) -> str:
    msgs = await db.messages.find({"conversation_id": conv_id}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    label = {"user": "Customer", "ai": "Assistant", "agent": "Assistant"}
    return "\n".join(f"{label[m['role']]}: {m['text']}" for m in reversed(msgs))


SPOKEN = (" This reply will be SPOKEN as a voice message: write natural spoken sentences only, no emoji, no symbols like $ % or /, "
          "write prices and numbers as words in the customer's language (e.g. in Khmer 'បីដុល្លារកន្លះ'), and do not mix in English words when replying in another language.")


async def generate_reply(conv_id: str, s: Settings, products: list, spoken: bool = False) -> str:
    t = await transcript(conv_id)
    prompt = f"Conversation so far:\n{t}\n\nWrite the assistant's next reply to the customer.{SPOKEN if spoken else ''} Output only the reply text."
    for attempt in range(3):
        try:
            return await llm(s, system_prompt(s, products), prompt)
        except Exception as e:
            if attempt == 2:
                raise
            logger.warning("AI reply retry %s: %s", attempt + 1, e)
            await asyncio.sleep(1.5 * (attempt + 1))


# ---------- Conversations core ----------
async def get_or_create_conv(bid: str, channel: str, external_id: str, name: str) -> dict:
    key = {"business_id": bid, "channel": channel, "external_id": external_id}
    conv = await db.conversations.find_one(key, {"_id": 0})
    if conv:
        return conv
    conv = {"id": str(uuid.uuid4()), **key, "name": name or "Guest",
            "ai_enabled": True, "unread": 0, "last_message": "", "created_at": now_iso(), "updated_at": now_iso()}
    try:
        await db.conversations.insert_one(dict(conv))
    except DuplicateKeyError:
        return await db.conversations.find_one(key, {"_id": 0})
    return conv


async def add_message(conv: dict, role: str, text: str, attachments: Optional[list] = None) -> dict:
    conv_id = conv["id"]
    msg = {"id": str(uuid.uuid4()), "conversation_id": conv_id, "business_id": conv["business_id"], "role": role, "text": text,
           "attachments": attachments or [], "created_at": now_iso()}
    await db.messages.insert_one(dict(msg))
    voice = any(a["type"] == "audio" for a in msg["attachments"])
    upd = {"$set": {"last_message": (("[Voice] " if voice else "") + text)[:140], "updated_at": msg["created_at"], "last_role": role}}
    if role == "user":
        upd["$inc"] = {"unread": 1}
    await db.conversations.update_one({"id": conv_id}, upd)
    return msg


async def send_to_channel(conv: dict, text: str, s: Settings):
    async with httpx.AsyncClient(timeout=20) as h:
        if conv["channel"] == "telegram" and s.telegram_token:
            r = await h.post(f"https://api.telegram.org/bot{s.telegram_token}/sendMessage", json={"chat_id": conv["external_id"], "text": text})
            logger.info("telegram send %s %s", r.status_code, r.text[:200])
        elif conv["channel"] == "messenger" and s.fb_page_token:
            r = await h.post("https://graph.facebook.com/v21.0/me/messages", params={"access_token": s.fb_page_token},
                             json={"recipient": {"id": conv["external_id"]}, "messaging_type": "RESPONSE", "message": {"text": text}})
            logger.info("messenger send %s %s", r.status_code, r.text[:200])


async def deliver(conv: dict, s: Settings, text: str, voice_mp3: Optional[bytes], products: list):
    ch, to = conv["channel"], conv["external_id"]
    if ch == "web" or not ((ch == "telegram" and s.telegram_token) or (ch == "messenger" and s.fb_page_token)):
        return
    if voice_mp3 is None:
        await send_to_channel(conv, text, s)
    async with httpx.AsyncClient(timeout=60) as h:
        try:
            if ch == "telegram":
                base = f"https://api.telegram.org/bot{s.telegram_token}"
                if voice_mp3 is not None:
                    r = await h.post(f"{base}/sendVoice", data={"chat_id": to}, files={"voice": ("reply.mp3", voice_mp3, "audio/mpeg")})
                    logger.info("telegram voice %s %s", r.status_code, r.text[:150])
                for p in products:
                    cap = f"{p['name']}" + (f" — {p['price']}" if p.get("price") else "")
                    img, doc = await M.load_media(db, p["image_media_id"]) if p.get("image_media_id") else (None, None)
                    if img:
                        r = await h.post(f"{base}/sendPhoto", data={"chat_id": to, "caption": cap}, files={"photo": ("product.jpg", img, doc["content_type"])})
                    else:
                        r = await h.post(f"{base}/sendMessage", json={"chat_id": to, "text": cap})
                    logger.info("telegram product %s %s", r.status_code, r.text[:150])
            else:
                url, params = "https://graph.facebook.com/v21.0/me/messages", {"access_token": s.fb_page_token}
                rcpt = json.dumps({"id": to})

                async def attach(kind, data, fname, ct):
                    msg = json.dumps({"attachment": {"type": kind, "payload": {"is_reusable": False}}})
                    r = await h.post(url, params=params, data={"recipient": rcpt, "message": msg, "messaging_type": "RESPONSE"}, files={"filedata": (fname, data, ct)})
                    logger.info("messenger %s %s %s", kind, r.status_code, r.text[:150])
                if voice_mp3 is not None:
                    await attach("audio", voice_mp3, "reply.mp3", "audio/mpeg")
                for p in products:
                    img, doc = await M.load_media(db, p["image_media_id"]) if p.get("image_media_id") else (None, None)
                    if img:
                        await attach("image", img, "product.jpg", doc["content_type"])
                    await send_to_channel(conv, f"{p['name']}" + (f" — {p['price']}" if p.get("price") else ""), s)
        except Exception as e:
            logger.exception("deliver failed: %s", e)


def product_att(p: dict) -> dict:
    return {"type": "product", "product_id": p["id"], "media_id": p.get("image_media_id") or None, "name": p["name"], "price": p.get("price", "")}


async def handle_incoming(bid: str, channel: str, external_id: str, name: str, text: str, audio: Optional[bytes] = None):
    conv = await get_or_create_conv(bid, channel, external_id, name)
    atts = []
    if audio:
        try:
            mp3 = await M.to_mp3(audio)
            vm = await M.save_media(db, bid, mp3, "audio/mpeg", "voice")
            atts.append({"type": "audio", "media_id": vm["id"]})
            text = await M.transcribe(mp3) or text
        except Exception as e:
            logger.exception("voice in failed: %s", e)
        text = text or "(voice message)"
    await add_message(conv, "user", text, atts)
    s = await get_settings(bid)
    if not (s.auto_reply and conv["ai_enabled"]):
        return None
    products = await load_products(bid)
    try:
        reply, shown = split_show(await generate_reply(conv["id"], s, products, spoken=bool(audio and s.voice_replies)), products)
    except Exception as e:
        logger.exception("AI reply failed: %s", e)
        return None
    ratts, voice_mp3 = [], None
    if audio and s.voice_replies:
        try:
            voice_mp3, engine = await M.speak(db, s, reply)
            vm = await M.save_media(db, bid, voice_mp3, "audio/mpeg", "voice")
            ratts.append({"type": "audio", "media_id": vm["id"], "engine": engine})
        except Exception as e:
            logger.exception("voice reply failed: %s", e)
            voice_mp3 = None
    ratts += [product_att(p) for p in shown]
    msg = await add_message(conv, "ai", reply, ratts)
    await deliver(conv, s, reply, voice_mp3, shown)
    return msg


# ---------- Public (website widget) ----------
DEFAULT_BID = {}


async def resolve_bid(bid: str) -> str:
    if bid == "default":
        if "v" not in DEFAULT_BID:
            admin = await db.users.find_one({"email": os.environ['ADMIN_EMAIL'].lower()}, {"_id": 0, "business_id": 1})
            DEFAULT_BID["v"] = admin["business_id"]
        return DEFAULT_BID["v"]
    if not await db.businesses.find_one({"id": bid}, {"_id": 1}):
        raise HTTPException(404, "Business not found")
    return bid


@api.get("/public/{bid}/info")
async def public_info(bid: str):
    s = await get_settings(await resolve_bid(bid))
    return {"business_name": s.business_name, "greeting": s.greeting}


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


@api.post("/public/{bid}/chat")
async def public_chat(bid: str, body: PublicChatIn, request: Request):
    bid = await resolve_bid(bid)
    if not body.text.strip():
        raise HTTPException(400, "Empty message")
    ip = client_ip(request)
    if not rate_ok([(f"s:{bid}:{body.session_id}", 6, 60), (f"ip:{ip}", 20, 60), (f"iph:{ip}", 150, 3600)]):
        raise HTTPException(429, "You're sending messages too fast. Please wait a moment and try again.")
    msg = await handle_incoming(bid, "web", body.session_id, body.name or "Website visitor", body.text.strip())
    return {"reply": msg}


@api.post("/public/{bid}/voice")
async def public_voice(bid: str, request: Request, session_id: str = Form(..., max_length=100), name: str = Form("Website visitor"),
                       file: UploadFile = File(...)):
    bid = await resolve_bid(bid)
    ip = client_ip(request)
    if not rate_ok([(f"s:{bid}:{session_id}", 6, 60), (f"ip:{ip}", 20, 60), (f"iph:{ip}", 150, 3600)]):
        raise HTTPException(429, "You're sending messages too fast. Please wait a moment and try again.")
    data = await file.read()
    if not data or len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "Voice message must be under 10 MB")
    return {"reply": await handle_incoming(bid, "web", session_id, name[:80], "", audio=data)}


@api.get("/public/{bid}/chat/{session_id}")
async def public_history(bid: str, session_id: str):
    bid = await resolve_bid(bid)
    conv = await db.conversations.find_one({"business_id": bid, "channel": "web", "external_id": session_id}, {"_id": 0})
    if not conv:
        return {"messages": []}
    msgs = await db.messages.find({"conversation_id": conv["id"]}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return {"messages": msgs}


# ---------- Webhooks ----------
def tg_secret(bid: str, token: str) -> str:
    return hashlib.sha256(f"{JWT_SECRET}:{bid}:{token}".encode()).hexdigest()


@api.post("/webhooks/telegram/{bid}")
async def telegram_webhook(bid: str, request: Request, bg: BackgroundTasks):
    s = await get_settings(bid)
    if not s.telegram_token or not hmac.compare_digest(request.headers.get("X-Telegram-Bot-Api-Secret-Token", ""), tg_secret(bid, s.telegram_token)):
        raise HTTPException(403, "Bad secret")
    data = await request.json()
    m = data.get("message") or {}
    frm = m.get("from", {})
    name = " ".join(filter(None, [frm.get("first_name"), frm.get("last_name")])) or frm.get("username") or "Telegram user"
    voice = m.get("voice") or m.get("audio")
    if m.get("text"):
        bg.add_task(handle_incoming, bid, "telegram", str(m["chat"]["id"]), name, m["text"])
    elif voice:
        bg.add_task(telegram_voice, bid, s.telegram_token, str(m["chat"]["id"]), name, voice["file_id"], m.get("caption") or "")
    return {"ok": True}


async def telegram_voice(bid, token, chat_id, name, file_id, caption):
    try:
        async with httpx.AsyncClient(timeout=60) as h:
            fp = (await h.get(f"https://api.telegram.org/bot{token}/getFile", params={"file_id": file_id})).json()["result"]["file_path"]
            audio = (await h.get(f"https://api.telegram.org/file/bot{token}/{fp}")).content
    except Exception as e:
        logger.exception("telegram voice download failed: %s", e)
        return
    await handle_incoming(bid, "telegram", chat_id, name, caption, audio=audio)


@api.get("/webhooks/messenger/{bid}")
async def messenger_verify(bid: str, request: Request):
    s = await get_settings(bid)
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and s.fb_verify_token and q.get("hub.verify_token") == s.fb_verify_token:
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(403, "Verification failed")


@api.post("/webhooks/messenger/{bid}")
async def messenger_webhook(bid: str, request: Request, bg: BackgroundTasks):
    raw = await request.body()
    s = await get_settings(bid)
    expected = "sha256=" + hmac.new(s.fb_app_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not s.fb_app_secret or not hmac.compare_digest(request.headers.get("X-Hub-Signature-256", ""), expected):
        raise HTTPException(403, "Invalid signature")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")
    for entry in data.get("entry", []):
        for ev in entry.get("messaging", []):
            msg = ev.get("message") or {}
            if not msg or msg.get("is_echo"):
                continue
            psid = ev["sender"]["id"]
            audio = next((a for a in msg.get("attachments", []) if a.get("type") == "audio"), None)
            if msg.get("text"):
                bg.add_task(handle_incoming, bid, "messenger", psid, f"Messenger user {psid[-4:]}", msg["text"])
            elif audio and audio.get("payload", {}).get("url"):
                bg.add_task(messenger_voice, bid, psid, audio["payload"]["url"])
    return {"ok": True}


async def messenger_voice(bid, psid, url):
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as h:
            audio = (await h.get(url)).content
    except Exception as e:
        logger.exception("messenger voice download failed: %s", e)
        return
    await handle_incoming(bid, "messenger", psid, f"Messenger user {psid[-4:]}", "", audio=audio)


# ---------- Admin inbox ----------
@api.get("/conversations")
async def list_convs(channel: Optional[str] = None, q: Optional[str] = None, before: Optional[str] = None, before_id: Optional[str] = None,
                     limit: int = Query(50, ge=1, le=100), user=Depends(current_user)):
    bid = user["business_id"]
    flt = {"business_id": bid}
    if channel and channel != "all":
        flt["channel"] = channel
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        hits = await db.messages.distinct("conversation_id", {"business_id": bid, "text": rx})
        flt["$or"] = [{"id": {"$in": hits}}, {"name": rx}, {"last_message": rx}]
    total = await db.conversations.count_documents(flt)
    if before:
        page = [{"updated_at": {"$lt": before}}, {"updated_at": before, "id": {"$lt": before_id or ""}}]
        flt = {"$and": [flt, {"$or": page}]}
    items = await db.conversations.find(flt, {"_id": 0}).sort([("updated_at", -1), ("id", -1)]).to_list(limit + 1)
    return {"items": items[:limit], "has_more": len(items) > limit, "total": total}


@api.get("/conversations/{cid}/messages")
async def conv_messages(cid: str, user=Depends(current_user)):
    await load_conv(cid, user["business_id"])
    msgs = await db.messages.find({"conversation_id": cid}, {"_id": 0}).sort("created_at", -1).to_list(300)
    return list(reversed(msgs))


@api.patch("/conversations/{cid}")
async def patch_conv(cid: str, body: ConvPatch, user=Depends(current_user)):
    await load_conv(cid, user["business_id"])
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if upd:
        await db.conversations.update_one({"id": cid}, {"$set": upd})
    return await load_conv(cid, user["business_id"])


async def load_conv(cid, bid):
    conv = await db.conversations.find_one({"id": cid, "business_id": bid}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


@api.post("/conversations/{cid}/reply")
async def manual_reply(cid: str, body: ReplyIn, user=Depends(current_user)):
    conv = await load_conv(cid, user["business_id"])
    if not body.text.strip():
        raise HTTPException(400, "Empty message")
    msg = await add_message(conv, "agent", body.text.strip())
    await db.conversations.update_one({"id": cid}, {"$set": {"unread": 0}})
    await send_to_channel(conv, body.text.strip(), await get_settings(user["business_id"]))
    return msg


@api.post("/conversations/{cid}/suggest")
async def suggest(cid: str, user=Depends(current_user)):
    await load_conv(cid, user["business_id"])
    s = await get_settings(user["business_id"])
    t = await transcript(cid)
    raw = await llm(s, system_prompt(s, await load_products(user["business_id"])), f"Conversation so far:\n{t}\n\nGive 3 different short ready-to-send replies to the customer's latest message "
                    "(e.g. one direct answer, one asking a clarifying question, one with a next step/offer). "
                    'Respond ONLY with a JSON array of 3 strings.')
    m = re.search(r"\[.*\]", raw, re.S)
    try:
        items = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        items = []
    items = [SHOW_TAG.sub("", str(i)).strip() for i in items if str(i).strip()][:3] or [SHOW_TAG.sub("", raw).strip()]
    return {"suggestions": items}


@api.post("/ai/test")
async def ai_test(body: TestAIIn, user=Depends(current_user)):
    s = await get_settings(user["business_id"])
    products = await load_products(user["business_id"])
    raw = await llm(s, system_prompt(s, products), f"Customer: {body.text}\n\nWrite the assistant's reply. Output only the reply text.")
    reply, shown = split_show(raw, products)
    return {"reply": reply, "products": [product_att(p) for p in shown]}


# ---------- Media, products, voice ----------
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@api.get("/media/{mid}")
async def get_media(mid: str, auth: Optional[str] = None):
    data, doc = await M.load_media(db, mid)
    if not data:
        raise HTTPException(404, "Not found")
    if doc["kind"] == "seller_voice":
        try:
            sub = jwt.decode(auth or "", JWT_SECRET, algorithms=[JWT_ALG])["sub"]
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Not authenticated")
        owner = await db.users.find_one({"id": sub}, {"_id": 0, "business_id": 1})
        if not owner or owner["business_id"] != doc["business_id"]:
            raise HTTPException(404, "Not found")
        return Response(data, media_type=doc["content_type"], headers={"Cache-Control": "private, no-store"})
    return Response(data, media_type=doc["content_type"], headers={"Cache-Control": "public, max-age=86400"})


@api.post("/media/image")
async def upload_image(file: UploadFile = File(...), user=Depends(current_user)):
    if file.content_type not in IMAGE_TYPES:
        raise HTTPException(400, "Please upload a JPG, PNG or WEBP image")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "Image must be under 5 MB")
    doc = await M.save_media(db, user["business_id"], data, file.content_type, "product")
    return {"id": doc["id"]}


@api.get("/products")
async def list_products(user=Depends(current_user)):
    return await load_products(user["business_id"])


@api.post("/products")
async def create_product(body: ProductIn, user=Depends(current_user)):
    bid = user["business_id"]
    if await db.products.count_documents({"business_id": bid, "is_deleted": False}) >= 300:
        raise HTTPException(400, "Product limit reached (300)")
    doc = {"id": str(uuid.uuid4()), "business_id": bid, **body.model_dump(), "is_deleted": False, "created_at": now_iso()}
    await db.products.insert_one(dict(doc))
    return doc


@api.put("/products/{pid}")
async def update_product(pid: str, body: ProductIn, user=Depends(current_user)):
    flt = {"id": pid, "business_id": user["business_id"], "is_deleted": False}
    if not (await db.products.update_one(flt, {"$set": body.model_dump()})).matched_count:
        raise HTTPException(404, "Product not found")
    return await db.products.find_one(flt, {"_id": 0})


@api.delete("/products/{pid}")
async def delete_product(pid: str, user=Depends(current_user)):
    res = await db.products.update_one({"id": pid, "business_id": user["business_id"], "is_deleted": False}, {"$set": {"is_deleted": True}})
    if not res.matched_count:
        raise HTTPException(404, "Product not found")
    return {"ok": True}


@api.post("/settings/seller-voice")
async def seller_voice(file: UploadFile = File(...), text: str = Form(""), user=Depends(current_user)):
    data = await file.read()
    if not data or len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "Voice sample must be under 10 MB")
    try:
        wav = await M.to_wav16k(data)
    except Exception:
        raise HTTPException(400, "Could not read this audio file")
    doc = await M.save_media(db, user["business_id"], wav, "audio/wav", "seller_voice")
    text = text.strip() or await M.transcribe(await M.to_mp3(data))
    await db.settings.update_one({"business_id": user["business_id"]}, {"$set": {"seller_voice_media_id": doc["id"], "seller_voice_text": text}})
    return {"media_id": doc["id"], "text": text}


@api.post("/voice/test")
async def voice_test(body: TestAIIn, user=Depends(current_user)):
    s = await get_settings(user["business_id"])
    try:
        audio, engine = await M.speak(db, s, body.text[:500])
    except Exception as e:
        raise HTTPException(502, f"Voice generation failed: {e}")
    doc = await M.save_media(db, user["business_id"], audio, "audio/mpeg", "voice_test")
    return {"media_id": doc["id"], "engine": engine}


@api.get("/stats")
async def stats(user=Depends(current_user)):
    bid = user["business_id"]
    res = {"total": await db.conversations.count_documents({"business_id": bid})}
    for ch in ["web", "telegram", "messenger"]:
        res[ch] = await db.conversations.count_documents({"business_id": bid, "channel": ch})
    res["ai_replies"] = await db.messages.count_documents({"business_id": bid, "role": "ai"})
    res["agent_replies"] = await db.messages.count_documents({"business_id": bid, "role": "agent"})
    return res


# ---------- Channels ----------
@api.post("/channels/telegram/connect")
async def telegram_connect(body: TelegramConnectIn, user=Depends(current_user)):
    bid = user["business_id"]
    s = await get_settings(bid)
    if not s.telegram_token:
        raise HTTPException(400, "Save your Telegram bot token first")
    url = f"{body.base_url.rstrip('/')}/api/webhooks/telegram/{bid}"
    async with httpx.AsyncClient(timeout=20) as h:
        me_r = (await h.get(f"https://api.telegram.org/bot{s.telegram_token}/getMe")).json()
        if not me_r.get("ok"):
            await db.settings.update_one({"business_id": bid}, {"$set": {"telegram_token": ""}})
            raise HTTPException(400, f"Telegram rejected the token: {me_r.get('description', 'invalid token')}")
        r = (await h.post(f"https://api.telegram.org/bot{s.telegram_token}/setWebhook", json={"url": url, "secret_token": tg_secret(bid, s.telegram_token)})).json()
    if not r.get("ok"):
        raise HTTPException(400, f"Webhook failed: {r.get('description')}")
    return {"ok": True, "bot": me_r["result"].get("username"), "webhook": url}


@api.get("/channels/status")
async def channels_status(user=Depends(current_user)):
    s = await get_settings(user["business_id"])
    tg = {"configured": bool(s.telegram_token), "connected": False, "bot": None}
    if s.telegram_token:
        try:
            async with httpx.AsyncClient(timeout=10) as h:
                info = (await h.get(f"https://api.telegram.org/bot{s.telegram_token}/getWebhookInfo")).json()
                me_r = (await h.get(f"https://api.telegram.org/bot{s.telegram_token}/getMe")).json()
            tg["connected"] = info.get("result", {}).get("url", "").endswith(f"/api/webhooks/telegram/{user['business_id']}")
            tg["last_error"] = info.get("result", {}).get("last_error_message")
            tg["bot"] = me_r.get("result", {}).get("username")
        except Exception:
            pass
    return {"telegram": tg, "messenger": {"configured": bool(s.fb_page_token and s.fb_verify_token and s.fb_app_secret)}}


WIDGET_JS = r"""(function(){
  if (window.__replyflow) return; window.__replyflow = 1;
  var s = document.currentScript, origin = new URL(s.src).origin;
  var biz = s.getAttribute('data-business') || 'default';
  var color = (s.getAttribute('data-color') || '#10B981');
  var side = s.getAttribute('data-position') === 'left' ? 'left' : 'right';
  function init(){
    var f = document.createElement('iframe');
    f.src = origin + '/embed?b=' + encodeURIComponent(biz) + '&site=' + encodeURIComponent(location.hostname);
    f.title = 'Chat'; f.allow = 'clipboard-write; microphone; autoplay';
    f.style.cssText = 'position:fixed;bottom:92px;' + side + ':20px;width:370px;max-width:calc(100vw - 40px);height:540px;max-height:calc(100vh - 120px);border:0;border-radius:16px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.35);z-index:2147483646;display:none;background:#0F1522';
    var b = document.createElement('button');
    b.setAttribute('aria-label', 'Open chat'); b.id = 'replyflow-bubble';
    b.style.cssText = 'position:fixed;bottom:20px;' + side + ':20px;width:58px;height:58px;border-radius:50%;border:0;cursor:pointer;background:' + color + ';color:#0B0F17;box-shadow:0 8px 30px rgba(0,0,0,.3);z-index:2147483647;display:flex;align-items:center;justify-content:center;transition:transform .2s';
    var chat = '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg>';
    var close = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>';
    b.innerHTML = chat;
    b.onmouseenter = function(){ b.style.transform = 'scale(1.06)'; };
    b.onmouseleave = function(){ b.style.transform = 'none'; };
    b.onclick = function(){ var open = f.style.display === 'none'; f.style.display = open ? 'block' : 'none'; b.innerHTML = open ? close : chat; };
    document.body.appendChild(f); document.body.appendChild(b);
  }
  if (document.body) init(); else document.addEventListener('DOMContentLoaded', init);
})();"""


@api.get("/widget.js")
async def widget_js():
    return Response(WIDGET_JS, media_type="application/javascript", headers={"Cache-Control": "public, max-age=300"})


SUMMARY_PROMPT = (
    "Analyse this customer conversation for the business owner. Respond ONLY with a JSON object with keys: "
    '"intent" (what the customer wants, max 5 words), "summary" (1-2 short sentences), '
    '"stage" (one of: "New lead", "Hot lead", "Question", "Support", "Complaint", "Resolved"), '
    '"details" (array of up to 4 short key facts like product, budget, location, date, contact - only if mentioned), '
    '"next_step" (one short recommended action for the business). Write in the same language as the customer.'
)


@api.post("/conversations/{cid}/summary")
async def conv_summary(cid: str, force: bool = False, user=Depends(current_user)):
    conv = await load_conv(cid, user["business_id"])
    count = await db.messages.count_documents({"conversation_id": cid})
    if not force and conv.get("summary") and conv.get("summary_count") == count:
        return conv["summary"]
    if not await db.messages.count_documents({"conversation_id": cid, "role": "user"}):
        return None
    s = await get_settings(user["business_id"])
    t = await transcript(cid, 40)
    lang = "the same language the customer writes in (English if the customer writes in English)" if s.language == "auto" else s.language
    raw = await llm(s, f"You are a sales & support analyst for '{s.business_name}'. Business info: {s.business_info or '(not provided)'}",
                    f"{SUMMARY_PROMPT} All values must be written in {lang}.\n\nConversation:\n{t}")
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        data = {}
    summary = {"intent": str(data.get("intent", ""))[:60], "summary": str(data.get("summary", raw))[:400],
               "stage": str(data.get("stage", "Question")), "details": [str(d) for d in data.get("details", [])][:4],
               "next_step": str(data.get("next_step", "")), "updated_at": now_iso()}
    await db.conversations.update_one({"id": cid}, {"$set": {"summary": summary, "summary_count": count}})
    return summary


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    try:
        await db.conversations.drop_index("channel_1_external_id_1")
    except OperationFailure:
        pass
    await db.conversations.create_index([("business_id", 1), ("channel", 1), ("external_id", 1)], unique=True)
    await db.conversations.create_index([("business_id", 1), ("updated_at", -1)])
    await db.conversations.create_index("id", unique=True)
    await db.messages.create_index([("conversation_id", 1), ("created_at", -1)])
    await db.messages.create_index([("business_id", 1), ("role", 1)])
    await db.businesses.create_index("id", unique=True)
    await db.settings.create_index("business_id", unique=True, partialFilterExpression={"business_id": {"$exists": True}})
    await db.users.create_index("id", unique=True)
    await db.products.create_index([("business_id", 1), ("is_deleted", 1), ("created_at", -1)])
    await db.media.create_index("id", unique=True)
    try:
        M.init_storage()
    except Exception as e:
        logger.error("Storage init failed: %s", e)
    email, pw = os.environ['ADMIN_EMAIL'].lower(), os.environ['ADMIN_PASSWORD']
    existing = await db.users.find_one({"email": email})
    if not existing:
        existing = {"id": str(uuid.uuid4()), "email": email, "password_hash": hash_pw(pw), "name": "Admin", "role": "superadmin", "created_at": now_iso()}
        await db.users.insert_one(dict(existing))
    elif not existing.get("password_hash") or not verify_pw(pw, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_pw(pw)}})
    await db.users.update_one({"email": email}, {"$set": {"role": "superadmin"}})
    if not existing.get("business_id"):
        await migrate_single_tenant(existing)


async def migrate_single_tenant(admin: dict):
    bid = str(uuid.uuid4())
    old = await db.settings.find_one({"key": "main"}, {"_id": 0, "key": 0})
    await db.businesses.insert_one({"id": bid, "name": (old or {}).get("business_name", "My Business"), "owner_id": admin["id"], "created_at": now_iso()})
    if old:
        await db.settings.update_one({"key": "main"}, {"$set": {"business_id": bid}, "$unset": {"key": ""}})
    else:
        await db.settings.insert_one({"business_id": bid, **Settings().model_dump()})
    missing = {"business_id": {"$exists": False}}
    for coll in (db.users, db.conversations, db.messages):
        await coll.update_many(missing, {"$set": {"business_id": bid}})
    logger.info("Migrated single-tenant data to business %s", bid)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

