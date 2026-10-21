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
from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, BackgroundTasks, Query
from fastapi.responses import PlainTextResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from fastapi.responses import Response
from collections import deque
import hashlib
import hmac
import time
from pydantic import BaseModel, Field
from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

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
    ident = f"{request.client.host}:{email}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("count", 0) >= 5 and datetime.fromisoformat(att["last"]) > datetime.now(timezone.utc) - timedelta(minutes=15):
        raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash") or not verify_pw(body.password, user["password_hash"]):
        await db.login_attempts.update_one({"identifier": ident}, {"$inc": {"count": 1}, "$set": {"last": now_iso()}}, upsert=True)
        raise HTTPException(401, "Invalid email or password")
    await db.login_attempts.delete_one({"identifier": ident})
    return issue_token(user)


def issue_token(user: dict) -> dict:
    token = jwt.encode({"sub": user["id"], "email": user["email"], "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "access"}, JWT_SECRET, algorithm=JWT_ALG)
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user.get("name"), "picture": user.get("picture"), "role": user.get("role")}}


class GoogleIn(BaseModel):
    session_id: str


@api.post("/auth/google")
async def google_login(body: GoogleIn):
    async with httpx.AsyncClient(timeout=20) as h:
        r = await h.get("https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data", headers={"X-Session-ID": body.session_id})
    if r.status_code != 200:
        raise HTTPException(401, "Google sign-in failed. Please try again.")
    g = r.json()
    email = g["email"].strip().lower()
    s = await get_settings()
    allowed = {e.strip().lower() for e in s.allowed_emails} | {os.environ['ADMIN_EMAIL'].lower()}
    if email not in allowed:
        raise HTTPException(403, f"{email} is not allowed. Sign in with your password and add it in AI Settings → Team access.")
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if user:
        await db.users.update_one({"email": email}, {"$set": {"picture": g.get("picture"), "name": user.get("name") or g.get("name")}})
        user["picture"] = g.get("picture")
    else:
        user = {"id": str(uuid.uuid4()), "email": email, "name": g.get("name"), "picture": g.get("picture"), "role": "admin", "auth": "google", "created_at": now_iso()}
        await db.users.insert_one(dict(user))
    return issue_token(user)


@api.get("/auth/me")
async def me(user=Depends(current_user)):
    return user


# ---------- Settings ----------
async def get_settings() -> Settings:
    doc = await db.settings.find_one({"key": "main"}, {"_id": 0, "key": 0})
    return Settings(**(doc or {}))


@api.get("/settings")
async def read_settings(user=Depends(current_user)):
    return (await get_settings()).model_dump()


@api.put("/settings")
async def write_settings(body: Settings, user=Depends(current_user)):
    await db.settings.update_one({"key": "main"}, {"$set": body.model_dump()}, upsert=True)
    return body.model_dump()


# ---------- AI ----------
TONES = {
    "friendly": "warm, friendly and upbeat",
    "professional": "polite, professional and precise",
    "direct": "short, direct and to the point",
    "witty": "light, witty and charming while staying helpful",
}


def system_prompt(s: Settings) -> str:
    faqs = "\n".join(f"Q: {f.q}\nA: {f.a}" for f in s.faqs) or "(none)"
    lang = "Always reply in the same language the customer writes in." if s.language == "auto" else f"Always reply in {s.language}."
    return (
        f"You are the customer support assistant for '{s.business_name}' (type: {s.business_type}).\n"
        f"Business information:\n{s.business_info or '(not provided)'}\n\nFAQs:\n{faqs}\n\n"
        f"Style: {TONES.get(s.tone, TONES['friendly'])}. Keep replies short (1-3 sentences), clear and easy to read on a phone. "
        f"Understand what the customer really wants, answer it directly, and suggest a next step when helpful. {lang} "
        "Only use the business information and FAQs for facts like prices, hours or policies; if you don't know, say a team member will follow up. "
        "Never mention you are an AI model name. Plain text only, no markdown."
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


async def generate_reply(conv_id: str, s: Settings) -> str:
    t = await transcript(conv_id)
    return await llm(s, system_prompt(s), f"Conversation so far:\n{t}\n\nWrite the assistant's next reply to the customer. Output only the reply text.")


# ---------- Conversations core ----------
async def get_or_create_conv(channel: str, external_id: str, name: str) -> dict:
    conv = await db.conversations.find_one({"channel": channel, "external_id": external_id}, {"_id": 0})
    if conv:
        return conv
    conv = {"id": str(uuid.uuid4()), "channel": channel, "external_id": external_id, "name": name or "Guest",
            "ai_enabled": True, "unread": 0, "last_message": "", "created_at": now_iso(), "updated_at": now_iso()}
    try:
        await db.conversations.insert_one(dict(conv))
    except DuplicateKeyError:
        return await db.conversations.find_one({"channel": channel, "external_id": external_id}, {"_id": 0})
    return conv


async def add_message(conv_id: str, role: str, text: str) -> dict:
    msg = {"id": str(uuid.uuid4()), "conversation_id": conv_id, "role": role, "text": text, "created_at": now_iso()}
    await db.messages.insert_one(dict(msg))
    upd = {"$set": {"last_message": text[:140], "updated_at": msg["created_at"], "last_role": role}}
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


async def handle_incoming(channel: str, external_id: str, name: str, text: str):
    conv = await get_or_create_conv(channel, external_id, name)
    await add_message(conv["id"], "user", text)
    s = await get_settings()
    if not (s.auto_reply and conv["ai_enabled"]):
        return None
    try:
        reply = await generate_reply(conv["id"], s)
    except Exception as e:
        logger.exception("AI reply failed: %s", e)
        return None
    msg = await add_message(conv["id"], "ai", reply)
    await send_to_channel(conv, reply, s)
    return msg


# ---------- Public (website widget) ----------
@api.get("/public/info")
async def public_info():
    s = await get_settings()
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


@api.post("/public/chat")
async def public_chat(body: PublicChatIn, request: Request):
    if not body.text.strip():
        raise HTTPException(400, "Empty message")
    ip = client_ip(request)
    if not rate_ok([(f"s:{body.session_id}", 6, 60), (f"ip:{ip}", 20, 60), (f"iph:{ip}", 150, 3600)]):
        raise HTTPException(429, "You're sending messages too fast. Please wait a moment and try again.")
    msg = await handle_incoming("web", body.session_id, body.name or "Website visitor", body.text.strip())
    return {"reply": msg}


@api.get("/public/chat/{session_id}")
async def public_history(session_id: str):
    conv = await db.conversations.find_one({"channel": "web", "external_id": session_id}, {"_id": 0})
    if not conv:
        return {"messages": []}
    msgs = await db.messages.find({"conversation_id": conv["id"]}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return {"messages": msgs}


# ---------- Webhooks ----------
def tg_secret(token: str) -> str:
    return hashlib.sha256(f"{JWT_SECRET}:{token}".encode()).hexdigest()


@api.post("/webhooks/telegram/{secret}")
async def telegram_webhook(secret: str, request: Request, bg: BackgroundTasks):
    s = await get_settings()
    if not s.telegram_token or secret != s.telegram_token.split(":")[0] or request.headers.get("X-Telegram-Bot-Api-Secret-Token") != tg_secret(s.telegram_token):
        raise HTTPException(403, "Bad secret")
    data = await request.json()
    m = data.get("message") or {}
    if m.get("text"):
        frm = m.get("from", {})
        name = " ".join(filter(None, [frm.get("first_name"), frm.get("last_name")])) or frm.get("username") or "Telegram user"
        bg.add_task(handle_incoming, "telegram", str(m["chat"]["id"]), name, m["text"])
    return {"ok": True}


@api.get("/webhooks/messenger")
async def messenger_verify(request: Request):
    s = await get_settings()
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and s.fb_verify_token and q.get("hub.verify_token") == s.fb_verify_token:
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(403, "Verification failed")


@api.post("/webhooks/messenger")
async def messenger_webhook(request: Request, bg: BackgroundTasks):
    raw = await request.body()
    s = await get_settings()
    expected = "sha256=" + hmac.new(s.fb_app_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not s.fb_app_secret or not hmac.compare_digest(request.headers.get("X-Hub-Signature-256", ""), expected):
        raise HTTPException(403, "Invalid signature")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")
    for entry in data.get("entry", []):
        for ev in entry.get("messaging", []):
            text = (ev.get("message") or {}).get("text")
            if text and not ev["message"].get("is_echo"):
                psid = ev["sender"]["id"]
                bg.add_task(handle_incoming, "messenger", psid, f"Messenger user {psid[-4:]}", text)
    return {"ok": True}


# ---------- Admin inbox ----------
@api.get("/conversations")
async def list_convs(channel: Optional[str] = None, q: Optional[str] = None, user=Depends(current_user)):
    flt = {}
    if channel and channel != "all":
        flt["channel"] = channel
    if q:
        hits = await db.messages.distinct("conversation_id", {"text": {"$regex": re.escape(q), "$options": "i"}})
        flt["$or"] = [{"id": {"$in": hits}}, {"name": {"$regex": re.escape(q), "$options": "i"}}, {"last_message": {"$regex": re.escape(q), "$options": "i"}}]
    return await db.conversations.find(flt, {"_id": 0}).sort("updated_at", -1).to_list(300)


@api.get("/conversations/{cid}/messages")
async def conv_messages(cid: str, user=Depends(current_user)):
    return await db.messages.find({"conversation_id": cid}, {"_id": 0}).sort("created_at", 1).to_list(1000)


@api.patch("/conversations/{cid}")
async def patch_conv(cid: str, body: ConvPatch, user=Depends(current_user)):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if upd:
        await db.conversations.update_one({"id": cid}, {"$set": upd})
    conv = await db.conversations.find_one({"id": cid}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Not found")
    return conv


async def load_conv(cid):
    conv = await db.conversations.find_one({"id": cid}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


@api.post("/conversations/{cid}/reply")
async def manual_reply(cid: str, body: ReplyIn, user=Depends(current_user)):
    conv = await load_conv(cid)
    if not body.text.strip():
        raise HTTPException(400, "Empty message")
    msg = await add_message(cid, "agent", body.text.strip())
    await db.conversations.update_one({"id": cid}, {"$set": {"unread": 0}})
    await send_to_channel(conv, body.text.strip(), await get_settings())
    return msg


@api.post("/conversations/{cid}/suggest")
async def suggest(cid: str, user=Depends(current_user)):
    await load_conv(cid)
    s = await get_settings()
    t = await transcript(cid)
    raw = await llm(s, system_prompt(s), f"Conversation so far:\n{t}\n\nGive 3 different short ready-to-send replies to the customer's latest message "
                    "(e.g. one direct answer, one asking a clarifying question, one with a next step/offer). "
                    'Respond ONLY with a JSON array of 3 strings.')
    m = re.search(r"\[.*\]", raw, re.S)
    try:
        items = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        items = []
    items = [str(i) for i in items if str(i).strip()][:3] or [raw]
    return {"suggestions": items}


@api.post("/ai/test")
async def ai_test(body: TestAIIn, user=Depends(current_user)):
    s = await get_settings()
    return {"reply": await llm(s, system_prompt(s), f"Customer: {body.text}\n\nWrite the assistant's reply. Output only the reply text.")}


@api.get("/stats")
async def stats(user=Depends(current_user)):
    res = {"total": await db.conversations.count_documents({})}
    for ch in ["web", "telegram", "messenger"]:
        res[ch] = await db.conversations.count_documents({"channel": ch})
    res["ai_replies"] = await db.messages.count_documents({"role": "ai"})
    res["agent_replies"] = await db.messages.count_documents({"role": "agent"})
    return res


# ---------- Channels ----------
@api.post("/channels/telegram/connect")
async def telegram_connect(body: TelegramConnectIn, user=Depends(current_user)):
    s = await get_settings()
    if not s.telegram_token:
        raise HTTPException(400, "Save your Telegram bot token first")
    url = f"{body.base_url.rstrip('/')}/api/webhooks/telegram/{s.telegram_token.split(':')[0]}"
    async with httpx.AsyncClient(timeout=20) as h:
        me_r = (await h.get(f"https://api.telegram.org/bot{s.telegram_token}/getMe")).json()
        if not me_r.get("ok"):
            await db.settings.update_one({"key": "main"}, {"$set": {"telegram_token": ""}})
            raise HTTPException(400, f"Telegram rejected the token: {me_r.get('description', 'invalid token')}")
        r = (await h.post(f"https://api.telegram.org/bot{s.telegram_token}/setWebhook", json={"url": url, "secret_token": tg_secret(s.telegram_token)})).json()
    if not r.get("ok"):
        raise HTTPException(400, f"Webhook failed: {r.get('description')}")
    return {"ok": True, "bot": me_r["result"].get("username"), "webhook": url}


@api.get("/channels/status")
async def channels_status(user=Depends(current_user)):
    s = await get_settings()
    tg = {"configured": bool(s.telegram_token), "connected": False, "bot": None}
    if s.telegram_token:
        try:
            async with httpx.AsyncClient(timeout=10) as h:
                info = (await h.get(f"https://api.telegram.org/bot{s.telegram_token}/getWebhookInfo")).json()
                me_r = (await h.get(f"https://api.telegram.org/bot{s.telegram_token}/getMe")).json()
            tg["connected"] = bool(info.get("result", {}).get("url"))
            tg["bot"] = me_r.get("result", {}).get("username")
        except Exception:
            pass
    return {"telegram": tg, "messenger": {"configured": bool(s.fb_page_token and s.fb_verify_token and s.fb_app_secret)}}


WIDGET_JS = r"""(function(){
  if (window.__replyflow) return; window.__replyflow = 1;
  var s = document.currentScript, origin = new URL(s.src).origin;
  var color = (s.getAttribute('data-color') || '#10B981');
  var side = s.getAttribute('data-position') === 'left' ? 'left' : 'right';
  function init(){
    var f = document.createElement('iframe');
    f.src = origin + '/embed?site=' + encodeURIComponent(location.hostname);
    f.title = 'Chat'; f.allow = 'clipboard-write';
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
    conv = await load_conv(cid)
    count = await db.messages.count_documents({"conversation_id": cid})
    if not force and conv.get("summary") and conv.get("summary_count") == count:
        return conv["summary"]
    if not await db.messages.count_documents({"conversation_id": cid, "role": "user"}):
        return None
    s = await get_settings()
    t = await transcript(cid, 40)
    raw = await llm(s, f"You are a sales & support analyst for '{s.business_name}'. Business info: {s.business_info or '(not provided)'}",
                    f"{SUMMARY_PROMPT}\n\nConversation:\n{t}")
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
    await db.conversations.create_index([("channel", 1), ("external_id", 1)], unique=True)
    await db.messages.create_index("conversation_id")
    email, pw = os.environ['ADMIN_EMAIL'].lower(), os.environ['ADMIN_PASSWORD']
    existing = await db.users.find_one({"email": email})
    if not existing:
        await db.users.insert_one({"id": str(uuid.uuid4()), "email": email, "password_hash": hash_pw(pw), "name": "Admin", "role": "admin", "created_at": now_iso()})
    elif not verify_pw(pw, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_pw(pw)}})


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

