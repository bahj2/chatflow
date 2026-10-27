"""One-click "Connect with Facebook": the platform's own Meta app logs the shop owner in, the owner picks a Page,
and we store that Page's token and subscribe the Page to our single app-level webhook (routed by Page ID)."""
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel

from core import db, logger, now_iso, current_user, owner_only, superadmin, get_settings  # loads .env first
import notion_kb as N  # noqa: E402
from routers.settings import FB_TAKEN, taken_by_other
from routers.webhooks import dispatch_messenger

router = APIRouter(prefix="/api")

GRAPH_VERSION = "v26.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
SCOPES = "pages_show_list,pages_messaging,pages_manage_metadata"
CALLBACK_PATH = "/api/meta/facebook/callback"
WEBHOOK_PATH = "/api/webhooks/meta/page"


def cfg() -> dict:
    return {k: (os.environ.get(f"META_{k}") or "").strip() for k in ("APP_ID", "APP_SECRET", "LOGIN_CONFIG_ID", "WEBHOOK_VERIFY_TOKEN")}


def available() -> bool:
    c = cfg()
    return bool(c["APP_ID"] and c["APP_SECRET"] and c["WEBHOOK_VERIFY_TOKEN"])


def now() -> datetime:
    return datetime.now(timezone.utc)


def clean_base(url: str) -> str:
    u = urlparse((url or "").strip())
    if u.scheme not in ("http", "https") or not u.netloc:
        raise HTTPException(400, "Invalid address")
    return f"{u.scheme}://{u.netloc}"


class GraphError(Exception):
    pass


async def graph(method: str, path: str, **params) -> dict:
    try:
        async with httpx.AsyncClient(timeout=20) as h:
            r = await h.request(method, f"{GRAPH}/{path.lstrip('/')}", params=params)
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise GraphError(f"Facebook could not be reached ({e.__class__.__name__}). Please try again.")
    if r.status_code >= 400 or "error" in data:
        err = data.get("error") or {}
        logger.warning("graph %s %s -> %s %s", method, path, r.status_code, str(err)[:200])
        raise GraphError(err.get("message") or f"Facebook error {r.status_code}")
    return data


# ---------- Shop owner: connect flow ----------
@router.get("/meta/status")
async def meta_status(user=Depends(current_user)):
    s = await get_settings(user["business_id"])
    return {"available": available(), "connected": bool(s.fb_oauth and s.fb_page_id), "page_id": s.fb_page_id if s.fb_oauth else "",
            "page_name": s.fb_page_name if s.fb_oauth else ""}


class StartIn(BaseModel):
    base_url: str    # this backend's public address (callback is registered in the Meta app)
    return_url: str  # the dashboard address to come back to


@router.post("/meta/facebook/start")
async def facebook_start(body: StartIn, user=Depends(owner_only)):
    if not available():
        raise HTTPException(503, "Connect with Facebook isn't set up yet. Ask Replyflow AI, or use manual setup below.")
    c = cfg()
    redirect_uri = clean_base(body.base_url) + CALLBACK_PATH
    state = secrets.token_urlsafe(32)
    await db.oauth_states.insert_one({"state": state, "business_id": user["business_id"], "redirect_uri": redirect_uri,
                                      "return_url": clean_base(body.return_url), "exp": now() + timedelta(minutes=10)})
    q = {"client_id": c["APP_ID"], "redirect_uri": redirect_uri, "state": state, "response_type": "code"}
    if c["LOGIN_CONFIG_ID"]:
        q["config_id"] = c["LOGIN_CONFIG_ID"]  # Facebook Login for Business configuration (permissions chosen in Meta)
    else:
        q["scope"] = SCOPES
    return {"url": f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth?{urlencode(q)}"}


@router.get("/meta/facebook/callback")
async def facebook_callback(code: str = "", state: str = "", error: str = "", error_description: str = ""):
    row = await db.oauth_states.find_one_and_delete({"state": state}) if state else None
    if not row or row["exp"].replace(tzinfo=timezone.utc) < now():
        raise HTTPException(400, "This Facebook sign-in link has expired. Go back to Channels and press Connect with Facebook again.")
    back = f"{row['return_url']}/dashboard/channels"
    if error or not code:
        return RedirectResponse(f"{back}?{urlencode({'fb_error': error_description or 'Facebook sign-in was cancelled.'})}")
    c = cfg()
    try:
        short = (await graph("GET", "oauth/access_token", client_id=c["APP_ID"], client_secret=c["APP_SECRET"],
                             redirect_uri=row["redirect_uri"], code=code))["access_token"]
        user_token = (await graph("GET", "oauth/access_token", grant_type="fb_exchange_token", client_id=c["APP_ID"],
                                  client_secret=c["APP_SECRET"], fb_exchange_token=short))["access_token"]
        pages = (await graph("GET", "me/accounts", fields="id,name", limit=100, access_token=user_token)).get("data", [])
    except GraphError as e:
        return RedirectResponse(f"{back}?{urlencode({'fb_error': str(e)})}")
    if not pages:
        return RedirectResponse(f"{back}?{urlencode({'fb_error': 'No Facebook Page was shared. Press Connect again and tick your Page, or make sure you are an admin of the Page.'})}")
    await db.fb_choices.update_one({"business_id": row["business_id"]}, {"$set": {
        "business_id": row["business_id"], "user_token_enc": N.seal(user_token),
        "pages": [{"id": str(p["id"]), "name": p.get("name") or ""} for p in pages], "exp": now() + timedelta(hours=1)}}, upsert=True)
    return RedirectResponse(f"{back}?fb=pick")


@router.get("/meta/facebook/pages")
async def facebook_pages(user=Depends(owner_only)):
    ch = await db.fb_choices.find_one({"business_id": user["business_id"]}, {"_id": 0})
    if not ch or ch["exp"].replace(tzinfo=timezone.utc) < now():
        raise HTTPException(404, "Press Connect with Facebook first.")
    return [{**p, "taken": await taken_by_other(user["business_id"], {"fb_page_id": p["id"]})} for p in ch["pages"]]


@router.post("/meta/facebook/pages/{page_id}/connect")
async def facebook_connect_page(page_id: str, user=Depends(owner_only)):
    bid = user["business_id"]
    ch = await db.fb_choices.find_one({"business_id": bid}, {"_id": 0})
    if not ch or ch["exp"].replace(tzinfo=timezone.utc) < now():
        raise HTTPException(404, "This Facebook sign-in has expired. Press Connect with Facebook again.")
    if page_id not in {p["id"] for p in ch["pages"]}:
        raise HTTPException(403, "This Page wasn't shared with Replyflow AI.")
    if await taken_by_other(bid, {"fb_page_id": page_id}):
        raise HTTPException(409, FB_TAKEN)
    try:
        page = await graph("GET", page_id, fields="id,name,access_token", access_token=N.unseal(ch["user_token_enc"]))
        if not page.get("access_token"):
            raise GraphError("Facebook didn't give access to this Page. Make sure you are an admin of the Page.")
        await graph("POST", f"{page_id}/subscribed_apps", subscribed_fields="messages", access_token=page["access_token"])
    except GraphError as e:
        raise HTTPException(400, str(e))
    cur = await get_settings(bid)
    if cur.fb_oauth and cur.fb_page_id and cur.fb_page_id != page_id:
        await unsubscribe(cur.fb_page_id, cur.fb_page_token)
    await db.settings.update_one({"business_id": bid}, {"$set": {
        "fb_page_token": page["access_token"], "fb_page_id": page_id, "fb_page_name": page.get("name") or "", "fb_oauth": True}})
    await db.fb_choices.delete_one({"business_id": bid})
    logger.info("facebook page %s connected to business %s at %s", page_id, bid, now_iso())
    return {"ok": True, "page_id": page_id, "page_name": page.get("name") or ""}


async def unsubscribe(page_id: str, token: str):
    try:
        await graph("DELETE", f"{page_id}/subscribed_apps", access_token=token)
    except GraphError as e:
        logger.info("unsubscribe %s: %s", page_id, e)


@router.delete("/meta/facebook")
async def facebook_disconnect(user=Depends(owner_only)):
    s = await get_settings(user["business_id"])
    if s.fb_oauth and s.fb_page_id:
        await unsubscribe(s.fb_page_id, s.fb_page_token)
        await db.settings.update_one({"business_id": user["business_id"]}, {"$set": {
            "fb_page_token": "", "fb_page_id": "", "fb_page_name": "", "fb_oauth": False}})
    return {"ok": True}


# ---------- Platform webhook (one URL for every shop, routed by Page ID) ----------
@router.get("/webhooks/meta/page")
async def meta_webhook_verify(request: Request):
    q, token = request.query_params, cfg()["WEBHOOK_VERIFY_TOKEN"]
    if q.get("hub.mode") == "subscribe" and token and hmac.compare_digest(q.get("hub.verify_token", ""), token):
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(403, "Verification failed")


@router.post("/webhooks/meta/page")
async def meta_webhook(request: Request, bg: BackgroundTasks):
    raw = await request.body()
    app_secret = cfg()["APP_SECRET"]
    expected = "sha256=" + hmac.new(app_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not app_secret or not hmac.compare_digest(request.headers.get("X-Hub-Signature-256", ""), expected):
        raise HTTPException(403, "Invalid signature")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")
    for entry in data.get("entry", []):
        s = await db.settings.find_one({"fb_page_id": str(entry.get("id", "")), "fb_oauth": True}, {"_id": 0, "business_id": 1})
        if s:
            dispatch_messenger(s["business_id"], entry, bg)
    return {"ok": True}


# ---------- Platform admin: what to paste into the Meta app ----------
@router.get("/admin/meta-setup")
async def meta_setup(base_url: str, user=Depends(superadmin)):
    c, base = cfg(), clean_base(base_url)
    return {"app_id_set": bool(c["APP_ID"]), "app_secret_set": bool(c["APP_SECRET"]), "config_id_set": bool(c["LOGIN_CONFIG_ID"]),
            "ready": available(), "redirect_uri": base + CALLBACK_PATH, "webhook_url": base + WEBHOOK_PATH,
            "verify_token": c["WEBHOOK_VERIFY_TOKEN"], "permissions": SCOPES.split(","), "graph_version": GRAPH_VERSION,
            "pages_connected": await db.settings.count_documents({"fb_oauth": True, "fb_page_id": {"$ne": ""}})}
