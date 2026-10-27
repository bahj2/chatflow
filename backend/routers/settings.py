import re

import httpx
from fastapi import APIRouter, HTTPException, Depends

import billing as B
import payments as P
from core import db, EMAIL_RE, Settings, get_settings, current_user

router = APIRouter(prefix="/api")


@router.get("/settings")
async def read_settings(user=Depends(current_user)):
    return (await get_settings(user["business_id"])).model_dump()


TG_TAKEN = "This Telegram bot is already connected to another shop. Each shop needs its own bot: create a new one with @BotFather."
FB_TAKEN = "This Facebook page is already connected to another shop. Each shop needs its own page."


def same_bot(token: str) -> dict:
    return {"telegram_token": {"$regex": f"^{re.escape(token.split(':', 1)[0])}:"}}  # same bot even after its token is revoked


async def taken_by_other(bid: str, query: dict) -> bool:
    return bool(await db.settings.find_one({"business_id": {"$ne": bid}, **query}, {"_id": 1}))


async def fb_page_id(token: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as h:
            return str((await h.get("https://graph.facebook.com/v21.0/me", params={"access_token": token, "fields": "id"})).json().get("id", ""))
    except Exception:
        return ""


@router.put("/settings")
async def write_settings(body: Settings, user=Depends(current_user)):
    bid = user["business_id"]
    body.allowed_emails = sorted({e.strip().lower() for e in body.allowed_emails if re.fullmatch(EMAIL_RE, e.strip())})
    cur = await get_settings(bid)
    team = (await B.sub_status(db, bid))["team"]
    if len(body.allowed_emails) > len(cur.allowed_emails) and len(body.allowed_emails) > team - 1:
        raise HTTPException(402, f"Your plan includes {team} login{'s' if team > 1 else ''}. Upgrade in Billing to add teammates.")
    body.telegram_token, body.fb_page_token = body.telegram_token.strip(), body.fb_page_token.strip()
    if body.telegram_token and body.telegram_token != cur.telegram_token and await taken_by_other(bid, same_bot(body.telegram_token)):
        raise HTTPException(409, TG_TAKEN)
    body.fb_page_id = cur.fb_page_id
    if body.fb_page_token and (body.fb_page_token != cur.fb_page_token or not cur.fb_page_id):
        body.fb_page_id = await fb_page_id(body.fb_page_token)
        if body.fb_page_id and await taken_by_other(bid, {"fb_page_id": body.fb_page_id}):
            raise HTTPException(409, FB_TAKEN)
    elif not body.fb_page_token:
        body.fb_page_id = ""
    if body.seller_voice_media_id != cur.seller_voice_media_id:
        body.seller_voice_text = cur.seller_voice_text  # stale tab: keep the transcript of the stored sample
    body.seller_voice_media_id = cur.seller_voice_media_id  # only /settings/seller-voice may change it
    body.seller_voice_text = body.seller_voice_text[:500]
    body.bakong_account_id, body.khqr_token = body.bakong_account_id.strip(), body.khqr_token.strip()
    if body.bakong_account_id and not P.ACCOUNT_RE.match(body.bakong_account_id):
        raise HTTPException(400, "Bakong account ID looks wrong. Example: name@aclb")
    if body.khqr_token and not body.khqr_token.startswith(P.RELAY_PREFIX):
        raise HTTPException(400, "KHQR.dev token must start with rbk")
    await db.settings.update_one({"business_id": bid}, {"$set": body.model_dump()}, upsert=True)
    await db.businesses.update_one({"id": bid}, {"$set": {"name": body.business_name}})
    return body.model_dump()
