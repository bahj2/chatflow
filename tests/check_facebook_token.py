"""Paste-a-Page-token connect (like Telegram). Graph API STUBBED (MOCKED)."""
import asyncio, os, sys, uuid
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv; load_dotenv('/app/backend/.env')
from fastapi import HTTPException, Request
import routers.meta as M
import routers.webhooks as W
from routers.settings import write_settings, read_settings
from routers.auth import create_business
from core import db, get_settings, Settings

CALLS = []
TOKENS = {"PAGE_OK": {"is_valid": True, "type": "PAGE", "app_id": "777"},
          "EXPIRED": {"is_valid": False, "type": "PAGE", "app_id": "777"},
          "USER_ONE": {"is_valid": True, "type": "USER", "app_id": "777"}}


async def fake_graph(method, path, **p):
    CALLS.append((method, path))
    if path == "debug_token":
        if p["input_token"] not in TOKENS:
            raise M.GraphError("Invalid OAuth access token")
        return {"data": TOKENS[p["input_token"]]}
    if path == "me/accounts":
        return {"data": [{"id": "PG9", "name": "Token Shop Page", "access_token": "PAGE_OK"}]}
    if path == "me":
        return {"id": "PG9", "name": "Token Shop Page"}
    if path == "oauth/access_token":
        if p["client_secret"] != "right-secret":
            raise M.GraphError("Error validating client secret")
        return {"access_token": "APP_TOK"}
    if path.endswith("/subscribed_apps"):
        return {"success": True}
    raise AssertionError(path)


class FakeResp:
    status_code = 200
    def json(self): return {"success": True}


class FakeClient:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def post(self, url, params=None, data=None):
        CALLS.append(("POST", url.split("/")[-1], data["callback_url"].split("/api")[1]))
        # Meta verifies the webhook right away with the verify token we just saved
        bid = data["callback_url"].rsplit("/", 1)[1]
        req = Request({"type": "http", "method": "GET", "headers": [], "query_string":
                       f"hub.mode=subscribe&hub.verify_token={data['verify_token']}&hub.challenge=777".encode()})
        res = await W.messenger_verify(bid, req)
        CALLS.append(("verify", res.body))
        return FakeResp()


async def main():
    M.graph = fake_graph
    M.httpx.AsyncClient = FakeClient
    uid = str(uuid.uuid4()); bid = await create_business("Token Shop", uid)
    user = {"id": uid, "business_id": bid, "role": "owner", "email": "t@x.com"}
    mk = lambda t, s: M.TokenIn(page_token=t, app_secret=s, base_url="https://api.x.com")  # noqa: E731
    for t, s, label in (("GARBAGE", "right-secret", "bad token"), ("EXPIRED", "right-secret", "expired"), ("PAGE_OK", "wrong", "wrong secret")):
        try:
            await M.facebook_token_connect(mk(t, s), user); print(label, "accepted (BAD)")
        except HTTPException as e:
            print(f"{label} -> {e.status_code}: {e.detail[:70]}")
    r = await M.facebook_token_connect(mk("PAGE_OK", "right-secret"), user)
    print("connect ->", r)
    print("webhook registered + verified:", [c for c in CALLS if c[0] in ("POST", "verify") and len(c) == 3 or c[0] == "verify"])
    st = await M.meta_status(user); print("status", st["connected"], st["via"], st["page_name"])
    s = await get_settings(bid); print("saved", s.fb_page_id, s.fb_page_token, s.fb_app_secret, bool(s.fb_verify_token), s.fb_oauth)
    # owner saves AI Settings with a stale blank form: connection must survive
    g = (await read_settings(user)); g.update(fb_page_token="", fb_app_secret="", business_info="x")
    await write_settings(Settings(**g), user)
    s = await get_settings(bid); print("after stale save still connected", s.fb_page_token == "PAGE_OK", s.fb_page_id)
    await M.facebook_disconnect(user)
    s = await get_settings(bid); print("disconnect clears", s.fb_page_token == "" and s.fb_page_id == "" and s.fb_app_secret == "")
    r = await M.facebook_token_connect(mk("USER_ONE", "right-secret"), user); print("personal token, one Page ->", r["page_name"])
    await db.users.delete_many({"business_id": bid})
    for c in ("settings", "subscriptions"):
        await db[c].delete_many({"business_id": bid})
    await db.businesses.delete_one({"id": bid})

asyncio.run(main())
