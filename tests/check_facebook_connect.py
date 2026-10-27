"""Connect-with-Facebook flow, end to end on our side. Facebook's Graph API is STUBBED (MOCKED): no real Meta app yet."""
import asyncio, hashlib, hmac, json, os, sys, uuid
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, '/app/backend')
os.environ.update(META_APP_ID='111', META_APP_SECRET='platform-secret', META_WEBHOOK_VERIFY_TOKEN='vt-123')

from fastapi import BackgroundTasks, HTTPException
import routers.meta as M
from routers.settings import write_settings, read_settings
from routers.auth import create_business
from core import db, get_settings, Settings

CALLS = []
PAGES = [{"id": "PAGE1", "name": "Dara Shop", "access_token": "PT_PAGE1"}, {"id": "PAGE2", "name": "Dara Shop 2", "access_token": "PT_PAGE2"}]


async def fake_graph(method, path, **p):
    CALLS.append((method, path))
    if path == "oauth/access_token":
        return {"access_token": "LONG_USER" if p.get("grant_type") else "SHORT_USER"}
    if path == "me/accounts":
        return {"data": PAGES}
    if method == "GET" and path in ("PAGE1", "PAGE2"):
        return {"id": path, "name": "Dara Shop" if path == "PAGE1" else "Dara Shop 2", "access_token": f"PT_{path}"}
    if path.endswith("/subscribed_apps"):
        return {"success": True}
    raise AssertionError(path)


class Req:
    def __init__(self, body=b"", headers=None, query=None):
        self._b, self.headers, self.query_params = body, headers or {}, query or {}
    async def body(self): return self._b


async def main():
    M.graph = fake_graph
    bid_a = await create_business("Shop A", "u-a"); bid_b = await create_business("Shop B", "u-b")
    A = {"business_id": bid_a, "role": "owner", "email": "a@x.com"}; Bu = {"business_id": bid_b, "role": "owner", "email": "b@x.com"}
    st = await M.meta_status(A); print("status before", st)
    r = await M.facebook_start(M.StartIn(base_url="https://api.example.com/", return_url="https://app.example.com"), A)
    q = parse_qs(urlparse(r["url"]).query)
    print("login url ok", r["url"].startswith("https://www.facebook.com/v26.0/dialog/oauth"), q["redirect_uri"], q["scope"])
    resp = await M.facebook_callback(code="CODE", state=q["state"][0])
    print("callback ->", resp.headers["location"])
    try:
        await M.facebook_callback(code="CODE", state=q["state"][0]); print("state reused (bad)")
    except HTTPException as e:
        print("reused state rejected", e.status_code)
    print("pages", await M.facebook_pages(A))
    res = await M.facebook_connect_page("PAGE1", A); print("connect", res)
    s = await get_settings(bid_a); print("saved", s.fb_oauth, s.fb_page_id, s.fb_page_name, s.fb_page_token)
    print("subscribed", ("POST", "PAGE1/subscribed_apps") in CALLS)
    g = await read_settings(A); print("browser sees page token?", bool(g["fb_page_token"]))
    # owner saves other settings with the blank token from the browser: connection must survive
    g["business_info"] = "new info"
    await write_settings(Settings(**g), A)
    s = await get_settings(bid_a); print("after save still connected", s.fb_oauth, s.fb_page_token == "PT_PAGE1", s.business_info)

    # shop B tries the same page
    r = await M.facebook_start(M.StartIn(base_url="https://api.example.com", return_url="https://app.example.com"), Bu)
    await M.facebook_callback(code="C", state=parse_qs(urlparse(r["url"]).query)["state"][0])
    print("B pages", await M.facebook_pages(Bu))
    try:
        await M.facebook_connect_page("PAGE1", Bu); print("B took page (bad)")
    except HTTPException as e:
        print("B blocked", e.status_code)

    # webhook from Meta for PAGE1
    body = json.dumps({"object": "page", "entry": [{"id": "PAGE1", "messaging": [{"sender": {"id": "555"}, "message": {"text": "Hi"}}]},
                                                   {"id": "UNKNOWN", "messaging": [{"sender": {"id": "9"}, "message": {"text": "x"}}]}]}).encode()
    good = "sha256=" + hmac.new(b"platform-secret", body, hashlib.sha256).hexdigest()
    try:
        await M.meta_webhook(Req(body, {"X-Hub-Signature-256": "sha256=bad"}), BackgroundTasks()); print("bad sig accepted (bad)")
    except HTTPException as e:
        print("bad signature", e.status_code)
    bg = BackgroundTasks()
    await M.meta_webhook(Req(body, {"X-Hub-Signature-256": good}), bg)
    print("routed tasks", [(t.args[0] == bid_a, t.args[1], t.args[2], t.args[4]) for t in bg.tasks])
    v = await M.meta_webhook_verify(Req(query={"hub.mode": "subscribe", "hub.verify_token": "vt-123", "hub.challenge": "42"}))
    print("verify", v.body)
    print("admin setup", await M.meta_setup("https://api.example.com", {"role": "superadmin"}))

    await M.facebook_disconnect(A)
    s = await get_settings(bid_a); print("disconnected", s.fb_oauth, s.fb_page_id == "", ("DELETE", "PAGE1/subscribed_apps") in CALLS)

    for b in (bid_a, bid_b):
        for c in ("settings", "fb_choices", "oauth_states", "businesses"):
            await db[c].delete_many({"business_id": b} if c != "businesses" else {"id": b})

asyncio.run(main())
