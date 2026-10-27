import httpx
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from core import db, get_settings, current_user
from routers.settings import TG_TAKEN, same_bot, taken_by_other
from routers.webhooks import tg_secret

router = APIRouter(prefix="/api")


class TelegramConnectIn(BaseModel):
    base_url: str

@router.post("/channels/telegram/connect")
async def telegram_connect(body: TelegramConnectIn, user=Depends(current_user)):
    bid = user["business_id"]
    s = await get_settings(bid)
    if not s.telegram_token:
        raise HTTPException(400, "Save your Telegram bot token first")
    if await taken_by_other(bid, same_bot(s.telegram_token)):
        raise HTTPException(409, TG_TAKEN)
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


@router.get("/channels/status")
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
