import json
import hashlib
import hmac

import httpx
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse

from core import JWT_SECRET, logger, get_settings
from replies import handle_incoming

router = APIRouter(prefix="/api")


def tg_secret(bid: str, token: str) -> str:
    return hashlib.sha256(f"{JWT_SECRET}:{bid}:{token}".encode()).hexdigest()


@router.post("/webhooks/telegram/{bid}")
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


@router.get("/webhooks/messenger/{bid}")
async def messenger_verify(bid: str, request: Request):
    s = await get_settings(bid)
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and s.fb_verify_token and q.get("hub.verify_token") == s.fb_verify_token:
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(403, "Verification failed")


@router.post("/webhooks/messenger/{bid}")
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
