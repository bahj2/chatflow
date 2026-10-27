"""Conversations and messages, and plain-text sending to Telegram / Messenger."""
import uuid
from typing import Optional

import httpx
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from core import db, logger, now_iso, Settings


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
    return {**conv, "is_new": True}


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

async def load_conv(cid, bid):
    conv = await db.conversations.find_one({"id": cid, "business_id": bid}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv
