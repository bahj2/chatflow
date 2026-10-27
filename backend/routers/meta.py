"""One-click "Connect with Facebook": the platform's own Meta app logs the shop owner in, the owner picks a Page,
and we store that Page's token and subscribe the Page to our single app-level webhook (routed by Page ID)."""
import hashlib
import hmac
import json
import os
import secrets
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel

from core import db, logger, now_iso, current_user, owner_only, superadmin, get_settings, is_owner, client_ip, rate_ok, member_problem  # loads .env first
import notion_kb as N  # noqa: E402
from routers.settings import FB_TAKEN, taken_by_other
from routers.webhooks import dispatch_messenger
from routers.auth import issue_token, sign_in_verified, create_business

router = APIRouter(prefix="/api")

GRAPH_VERSION = "v26.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
SCOPES = "pages_show_list,pages_messaging,pages_manage_metadata"
LOGIN_SCOPES = "public_profile,email," + SCOPES  # sign in AND share the Page in one Facebook step
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
    ch = await db.fb_choices.find_one({"business_id": user["business_id"]}, {"_id": 0, "exp": 1})
    pending = bool(ch and ch["exp"].replace(tzinfo=timezone.utc) > now())  # came back from Facebook, Page not picked yet
    u = await db.users.find_one({"id": user.get("id")}, {"_id": 0, "fb_token_exp": 1}) or {}
    remembered = bool(u.get("fb_token_exp") and u["fb_token_exp"].replace(tzinfo=timezone.utc) > now())
    return {"available": available(), "connected": bool(s.fb_oauth and s.fb_page_id), "page_id": s.fb_page_id if s.fb_oauth else "",
            "page_name": s.fb_page_name if s.fb_oauth else "", "pending": pending, "remembered": remembered}


class StartIn(BaseModel):
    base_url: str    # this backend's public address (callback is registered in the Meta app)
    return_url: str  # the dashboard address to come back to
    popup: bool = False  # Facebook opened in a small window over our site: come back to /fb-done, which closes it


@router.post("/meta/facebook/start")
async def facebook_start(body: StartIn, user=Depends(owner_only)):
    if not available():
        raise HTTPException(503, "Connect with Facebook isn't set up yet. Ask Replyflow AI, or use manual setup below.")
    c = cfg()
    redirect_uri = clean_base(body.base_url) + CALLBACK_PATH
    state = secrets.token_urlsafe(32)
    await db.oauth_states.insert_one({"state": state, "business_id": user["business_id"], "user_id": user.get("id"), "redirect_uri": redirect_uri,
                                      "return_url": clean_base(body.return_url), "popup": body.popup, "exp": now() + timedelta(minutes=10)})
    q = {"client_id": c["APP_ID"], "redirect_uri": redirect_uri, "state": state, "response_type": "code"}
    if body.popup:
        q["display"] = "popup"
    if c["LOGIN_CONFIG_ID"]:
        q["config_id"] = c["LOGIN_CONFIG_ID"]  # Facebook Login for Business configuration (permissions chosen in Meta)
    else:
        q["scope"] = SCOPES
    return {"url": f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth?{urlencode(q)}"}


@router.post("/meta/facebook/quick")
async def facebook_quick(body: StartIn, user=Depends(owner_only)):
    """Connect button: if this person already approved Facebook (sign-in or earlier connect), connect at once with no
    Facebook screens. Otherwise return the Facebook login address."""
    bid = user["business_id"]
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0, "fb_user_token_enc": 1, "fb_token_exp": 1})
    tok = None
    if u and u.get("fb_user_token_enc") and u.get("fb_token_exp") and u["fb_token_exp"].replace(tzinfo=timezone.utc) > now():
        tok = N.unseal(u["fb_user_token_enc"])
    if tok and available():
        try:
            pages = await shared_pages(tok)
        except GraphError:  # approval removed or expired on Facebook's side
            pages = None
            await db.users.update_one({"id": user["id"]}, {"$unset": {"fb_user_token_enc": "", "fb_token_exp": ""}})
        if pages:
            await save_choice(bid, tok, pages)
            free = [p for p in pages if not await taken_by_other(bid, {"fb_page_id": str(p["id"])})]
            if len(pages) == 1 and free:
                return {"connected": True, **await facebook_connect_page(str(free[0]["id"]), user)}
            return {"pick": True}
    return {"url": (await facebook_start(body, user))["url"]}


@router.get("/meta/facebook/callback")
async def facebook_callback(code: str = "", state: str = "", error: str = "", error_description: str = ""):
    row = await db.oauth_states.find_one_and_delete({"state": state}) if state else None
    if not row or row["exp"].replace(tzinfo=timezone.utc) < now():
        raise HTTPException(400, "This Facebook sign-in link has expired. Go back to Channels and press Connect with Facebook again.")
    if row.get("purpose") == "login":
        return await finish_facebook_login(row, code, error_description or error)
    back = f"{row['return_url']}/fb-done" if row.get("popup") else f"{row['return_url']}/dashboard/channels"
    if error or not code:
        return RedirectResponse(f"{back}?{urlencode({'fb_error': error_description or 'Facebook sign-in was cancelled.'})}")
    c = cfg()
    try:
        user_token = await user_token_from_code(c, row["redirect_uri"], code)
        pages = await shared_pages(user_token)
    except GraphError as e:
        return RedirectResponse(f"{back}?{urlencode({'fb_error': str(e)})}")
    if row.get("user_id"):
        await remember_token(row["user_id"], user_token)
    if not pages:
        return RedirectResponse(f"{back}?{urlencode({'fb_error': 'No Facebook Page was shared. Press Connect again and tick your Page, or make sure you are an admin of the Page.'})}")
    await save_choice(row["business_id"], user_token, pages)
    return RedirectResponse(f"{back}?fb=pick")


async def user_token_from_code(c: dict, redirect_uri: str, code: str) -> str:
    short = (await graph("GET", "oauth/access_token", client_id=c["APP_ID"], client_secret=c["APP_SECRET"],
                         redirect_uri=redirect_uri, code=code))["access_token"]
    return (await graph("GET", "oauth/access_token", grant_type="fb_exchange_token", client_id=c["APP_ID"],
                        client_secret=c["APP_SECRET"], fb_exchange_token=short))["access_token"]


async def shared_pages(user_token: str) -> list:
    # /me/accounts already returns each Page's own token (only pages_show_list needed, no extra permission)
    return (await graph("GET", "me/accounts", fields="id,name,access_token", limit=100, access_token=user_token)).get("data", [])


async def remember_token(user_id: str, user_token: str):
    """Keeps the person's (60-day) Facebook approval, sealed, so the next Connect needs no Facebook screens."""
    await db.users.update_one({"id": user_id}, {"$set": {"fb_user_token_enc": N.seal(user_token), "fb_token_exp": now() + timedelta(days=55)}})


async def save_choice(bid: str, user_token: str, pages: list):
    await db.fb_choices.update_one({"business_id": bid}, {"$set": {
        "business_id": bid, "user_token_enc": N.seal(user_token),
        "pages": [{"id": str(p["id"]), "name": p.get("name") or "", "token_enc": N.seal(p["access_token"]) if p.get("access_token") else ""}
                  for p in pages], "exp": now() + timedelta(hours=1)}}, upsert=True)


# ---------- "Continue with Facebook" sign-in / sign-up (same Meta app, same callback address) ----------
@router.get("/auth/facebook/available")
async def facebook_login_available():
    return {"available": available()}


@router.post("/auth/facebook/start")
async def facebook_login_start(body: StartIn, request: Request):
    if not available():
        raise HTTPException(503, "Facebook sign-in isn't switched on yet. Please use email or Google.")
    if not await rate_ok([(f"fblogin:{client_ip(request)}", 30, 3600)]):
        raise HTTPException(429, "Too many attempts from this network. Try again later.")
    c = cfg()
    state = secrets.token_urlsafe(32)
    redirect_uri = clean_base(body.base_url) + CALLBACK_PATH
    await db.oauth_states.insert_one({"state": state, "purpose": "login", "business_id": None, "redirect_uri": redirect_uri,
                                      "return_url": clean_base(body.return_url), "exp": now() + timedelta(minutes=10)})
    q = {"client_id": c["APP_ID"], "redirect_uri": redirect_uri, "state": state, "response_type": "code"}
    if c["LOGIN_CONFIG_ID"]:
        q["config_id"] = c["LOGIN_CONFIG_ID"]
    else:
        q["scope"] = LOGIN_SCOPES
    return {"url": f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth?{urlencode(q)}"}


async def finish_facebook_login(row: dict, code: str, error: str):
    fail = lambda msg: RedirectResponse(f"{row['return_url']}/login?{urlencode({'fb_error': msg})}")  # noqa: E731
    if error or not code:
        return fail("Facebook sign-in was cancelled." if not error or "denied" in error.lower() or "permission" in error.lower() else error)
    try:
        user_token = await user_token_from_code(cfg(), row["redirect_uri"], code)
        me = await graph("GET", "me", fields="id,name,email,picture.type(large)", access_token=user_token)
        pages = await shared_pages(user_token)
    except GraphError as e:
        return fail(str(e))
    fb_uid, name = str(me["id"]), me.get("name") or "Facebook user"
    picture = ((me.get("picture") or {}).get("data") or {}).get("url")
    password_off, created = False, False
    user = await db.users.find_one({"fb_uid": fb_uid}, {"_id": 0})
    try:
        if user:
            problem = await member_problem(user)
            if problem:
                raise HTTPException(403, problem)
            await db.users.update_one({"id": user["id"]}, {"$set": {"picture": picture or user.get("picture")}})
        elif me.get("email"):  # Facebook only shares emails it has confirmed
            user, password_off, created = await sign_in_verified(me["email"], name, picture, "facebook")
            await db.users.update_one({"id": user["id"]}, {"$set": {"fb_uid": fb_uid}})
        else:  # Facebook account without an email: the Facebook ID is the identity
            uid = str(uuid4())
            bid = await create_business(f"{name}'s business", uid)
            user = {"id": uid, "email": f"fb-{fb_uid}@facebook.local", "name": name, "picture": picture, "role": "owner",
                    "auth": "facebook", "fb_uid": fb_uid, "business_id": bid, "email_verified": True, "created_at": now_iso()}
            await db.users.insert_one(dict(user))
            created = True
    except HTTPException as e:
        return fail(e.detail)
    bid = user["business_id"]
    await remember_token(user["id"], user_token)
    if created and user.get("role") == "owner" and pages:  # new shop: name it after the Page
        shop = (pages[0].get("name") or "").strip()[:80]
        if shop:
            await db.businesses.update_one({"id": bid}, {"$set": {"name": shop}})
            await db.settings.update_one({"business_id": bid}, {"$set": {"business_name": shop}})
    pending = False
    if pages and is_owner(user):
        s = await get_settings(bid)
        if not (s.fb_oauth and s.fb_page_id):  # not connected yet: the Page they just ticked connects on the next screen
            await save_choice(bid, user_token, pages)
            pending = True
    one_time = secrets.token_urlsafe(32)
    await db.login_codes.insert_one({"code": one_time, "user_id": user["id"], "password_off": password_off, "pending": pending,
                                     "new": created, "exp": now() + timedelta(minutes=2)})
    return RedirectResponse(f"{row['return_url']}/auth/facebook?{urlencode({'code': one_time})}")


class FinishIn(BaseModel):
    code: str


@router.post("/auth/facebook/finish")
async def facebook_login_finish(body: FinishIn):
    """Swaps the one-time code from the Facebook redirect for a normal session (the session token never sits in a URL)."""
    row = await db.login_codes.find_one_and_delete({"code": body.code})
    if not row or row["exp"].replace(tzinfo=timezone.utc) < now():
        raise HTTPException(401, "This Facebook sign-in has expired. Please press Continue with Facebook again.")
    user = await db.users.find_one({"id": row["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(401, "Account not found")
    problem = await member_problem(user)
    if problem:
        raise HTTPException(403, problem)
    return {**await issue_token(user), "password_off": row["password_off"], "pending_pages": row["pending"], "new": row["new"]}


@router.get("/meta/facebook/pages")
async def facebook_pages(user=Depends(owner_only)):
    ch = await db.fb_choices.find_one({"business_id": user["business_id"]}, {"_id": 0})
    if not ch or ch["exp"].replace(tzinfo=timezone.utc) < now():
        raise HTTPException(404, "Press Connect with Facebook first.")
    return [{"id": p["id"], "name": p["name"], "taken": await taken_by_other(user["business_id"], {"fb_page_id": p["id"]})} for p in ch["pages"]]


@router.post("/meta/facebook/pages/{page_id}/connect")
async def facebook_connect_page(page_id: str, user=Depends(owner_only)):
    bid = user["business_id"]
    ch = await db.fb_choices.find_one({"business_id": bid}, {"_id": 0})
    if not ch or ch["exp"].replace(tzinfo=timezone.utc) < now():
        raise HTTPException(404, "This Facebook sign-in has expired. Press Connect with Facebook again.")
    chosen = next((p for p in ch["pages"] if p["id"] == page_id), None)
    if not chosen:
        raise HTTPException(403, "This Page wasn't shared with Replyflow AI.")
    if not chosen.get("token_enc"):
        raise HTTPException(400, "Facebook didn't give access to this Page. Press Connect with Facebook again and make sure you are an admin of the Page.")
    if await taken_by_other(bid, {"fb_page_id": page_id}):
        raise HTTPException(409, FB_TAKEN)
    page = {"name": chosen["name"], "access_token": N.unseal(chosen["token_enc"])}
    try:
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
async def app_token(c: dict) -> str:
    return (await graph("GET", "oauth/access_token", client_id=c["APP_ID"], client_secret=c["APP_SECRET"],
                        grant_type="client_credentials"))["access_token"]


async def webhook_state(c: dict) -> dict:
    """The Page webhook registered on the Meta app (url + active), or {} if none / keys missing."""
    if not available():
        return {}
    try:
        subs = (await graph("GET", f"{c['APP_ID']}/subscriptions", access_token=await app_token(c))).get("data", [])
    except GraphError:
        return {}
    page = next((x for x in subs if x.get("object") == "page"), None)
    return {"url": page.get("callback_url", ""), "active": bool(page.get("active")),
            "messages": any(f.get("name") == "messages" for f in page.get("fields", []))} if page else {}


class BaseIn(BaseModel):
    base_url: str


@router.post("/admin/meta-setup/webhook")
async def meta_setup_webhook(body: BaseIn, user=Depends(superadmin)):
    """One click instead of pasting the Callback URL + Verify token into Meta: registers our Page webhook on the app."""
    if not available():
        raise HTTPException(400, "Add the App ID and App secret first.")
    c, url = cfg(), clean_base(body.base_url) + WEBHOOK_PATH
    try:
        async with httpx.AsyncClient(timeout=30) as h:
            r = await h.post(f"{GRAPH}/{c['APP_ID']}/subscriptions", params={"access_token": await app_token(c)},
                             data={"object": "page", "callback_url": url, "fields": "messages", "verify_token": c["WEBHOOK_VERIFY_TOKEN"]})
        data = r.json()
    except GraphError as e:
        raise HTTPException(400, str(e))
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, "Facebook could not be reached. Please try again.")
    if r.status_code >= 400 or not data.get("success"):
        raise HTTPException(400, (data.get("error") or {}).get("message") or "Facebook refused the webhook")
    return {"ok": True, "webhook": await webhook_state(c)}


@router.get("/admin/meta-setup")
async def meta_setup(base_url: str, user=Depends(superadmin)):
    c, base = cfg(), clean_base(base_url)
    return {"app_id_set": bool(c["APP_ID"]), "app_secret_set": bool(c["APP_SECRET"]), "config_id_set": bool(c["LOGIN_CONFIG_ID"]),
            "ready": available(), "redirect_uri": base + CALLBACK_PATH, "webhook_url": base + WEBHOOK_PATH,
            "verify_token": c["WEBHOOK_VERIFY_TOKEN"], "permissions": SCOPES.split(","), "graph_version": GRAPH_VERSION,
            "pages_connected": await db.settings.count_documents({"fb_oauth": True, "fb_page_id": {"$ne": ""}}),
            "webhook": await webhook_state(c)}
