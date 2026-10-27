import os
import re
import hmac
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

import notion_kb as N
from core import db, now_iso, current_user, require_pro, rate_ok

router = APIRouter(prefix="/api")


class NotionConnectIn(BaseModel):
    token: str = Field(min_length=10, max_length=300)


async def notion_view(bid: str) -> dict:
    link = await db.notion_links.find_one({"business_id": bid}, {"_id": 0, "token_enc": 0, "knowledge": 0})
    if not link:
        return {"connected": False}
    pages = await db.notion_docs.find({"business_id": bid}, {"_id": 0, "title": 1, "url": 1, "kind": 1, "chars": 1}).sort([("kind", 1), ("title", 1)]).to_list(400)
    return {"connected": True, "pages": pages, **{k: link.get(k) for k in (
        "workspace", "bot_name", "hint", "status", "last_sync_at", "last_error", "page_count", "chars", "truncated", "connected_at")}}


@router.get("/notion")
async def notion_status(user=Depends(current_user)):
    return await notion_view(user["business_id"])


@router.post("/notion/connect")
async def notion_connect(body: NotionConnectIn, bg: BackgroundTasks, user=Depends(current_user)):
    await require_pro(user["business_id"])
    if not rate_ok([(f"nconn:{user['business_id']}", 10, 3600)]):
        raise HTTPException(429, "Too many tries. Please wait a few minutes.")
    token = body.token.strip()
    if not re.fullmatch(r"(ntn_|secret_)[A-Za-z0-9_-]{10,}", token):
        raise HTTPException(400, "This doesn't look like a Notion secret. It starts with ntn_")
    try:
        me = await N.whoami(token)
    except N.NotionError as e:
        raise HTTPException(400, N.friendly(e))
    bid = user["business_id"]
    await db.notion_docs.delete_many({"business_id": bid})
    await db.notion_links.update_one({"business_id": bid}, {"$set": {
        "business_id": bid, "token_enc": N.seal(token), "hint": token[-4:], "bot_name": me.get("name") or "",
        "workspace": (me.get("bot") or {}).get("workspace_name") or "", "connected_at": now_iso(), "status": "queued",
        "last_error": "", "knowledge": "", "page_count": 0, "chars": 0, "truncated": False, "last_sync_at": None}}, upsert=True)
    bg.add_task(N.sync_business, db, bid)
    return await notion_view(bid)


@router.post("/notion/sync")
async def notion_sync_now(bg: BackgroundTasks, user=Depends(current_user)):
    bid = user["business_id"]
    await require_pro(bid)
    if not rate_ok([(f"nsync:{bid}", 30, 3600)]):
        raise HTTPException(429, "Too many syncs. Please wait a few minutes.")
    res = await db.notion_links.update_one({"business_id": bid, "status": {"$ne": "syncing"}}, {"$set": {"status": "queued"}})
    if not res.matched_count and not await db.notion_links.find_one({"business_id": bid}, {"_id": 1}):
        raise HTTPException(400, "Connect Notion first")
    bg.add_task(N.sync_business, db, bid)
    return await notion_view(bid)


@router.delete("/notion")
async def notion_disconnect(user=Depends(current_user)):
    await db.notion_links.delete_one({"business_id": user["business_id"]})
    await db.notion_docs.delete_many({"business_id": user["business_id"]})
    return {"connected": False}


@router.post("/cron/notion-sync")
async def cron_notion_sync(request: Request, bg: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("Authorization", "")
    if not hmac.compare_digest(auth.encode(), f"Bearer {os.environ['WEBHOOK_CRON_SECRET']}".encode()):
        raise HTTPException(401, "Unauthorized")
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, "Invalid body")
    if not isinstance(body, dict):
        raise HTTPException(400, "Invalid body")
    run_id = request.headers.get("X-Webhook-Id") or str(body.get("run_id") or "")
    if run_id:
        try:
            await db.cron_runs.insert_one({"id": f"notion:{run_id}", "created": datetime.now(timezone.utc)})
        except DuplicateKeyError:
            return {"ok": True, "duplicate": True}
    bg.add_task(N.sync_all, db)
    return {"ok": True}
