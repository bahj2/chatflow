import re

import httpx
from fastapi import APIRouter, HTTPException, Depends

import billing as B
import payments as P
from core import db, EMAIL_RE, Settings, get_settings, current_user, is_owner

router = APIRouter(prefix="/api")


# Payment account, channel keys and team list: only the shop owner may see the secrets or change these.
OWNER_FIELDS = ("allowed_emails", "telegram_token", "fb_page_token", "fb_app_secret", "fb_verify_token",
                "bakong_account_id", "bakong_merchant_name", "bakong_city", "khqr_token", "seller_voice_text")
SECRET_FIELDS = ("telegram_token", "fb_page_token", "fb_app_secret", "fb_verify_token", "khqr_token")


def for_user(s: Settings, user: dict) -> dict:
    d = s.model_dump()
    if s.fb_oauth:
        d["fb_page_token"] = ""  # connected with Facebook login: the Page token never goes to the browser
    if not is_owner(user):
        d.update({k: "" for k in SECRET_FIELDS})
    return d


@router.get("/settings")
async def read_settings(user=Depends(current_user)):
    return for_user(await get_settings(user["business_id"]), user)


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
    if not is_owner(user):
        cur = await get_settings(bid)
        body = body.model_copy(update={k: getattr(cur, k) for k in OWNER_FIELDS})
    body.allowed_emails = sorted({e.strip().lower() for e in body.allowed_emails if re.fullmatch(EMAIL_RE, e.strip())})
    cur = await get_settings(bid)
    team = (await B.sub_status(db, bid))["team"]
    if len(body.allowed_emails) > len(cur.allowed_emails) and len(body.allowed_emails) > team - 1:
        raise HTTPException(402, f"Your plan includes {team} login{'s' if team > 1 else ''}. Upgrade in Billing to add teammates.")
    body.telegram_token, body.fb_page_token = body.telegram_token.strip(), body.fb_page_token.strip()
    if body.telegram_token and body.telegram_token != cur.telegram_token and await taken_by_other(bid, same_bot(body.telegram_token)):
        raise HTTPException(409, TG_TAKEN)
    body.fb_oauth, body.fb_page_name = cur.fb_oauth, cur.fb_page_name  # only the Connect with Facebook flow changes these
    if cur.fb_oauth:
        body.fb_page_token = cur.fb_page_token
    elif body.fb_page_token != cur.fb_page_token:
        body.fb_page_name = ""
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
    return for_user(body, user)
