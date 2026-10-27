"""'Continue with Facebook' sign-in, on our side. Facebook's Graph API is STUBBED (MOCKED)."""
import asyncio, os, sys, uuid
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv; load_dotenv('/app/backend/.env')
os.environ.update(META_APP_ID='111', META_APP_SECRET='platform-secret', META_WEBHOOK_VERIFY_TOKEN='vt-123')

from fastapi import HTTPException
import routers.meta as M
import routers.auth as A
from core import db, current_user, get_settings

TAG = uuid.uuid4().hex[:6]
ME = {}
PAGES = []


async def fake_graph(method, path, **p):
    if path == "oauth/access_token":
        return {"access_token": "LONG" if p.get("grant_type") else "SHORT"}
    if path == "me":
        return dict(ME)
    if path == "me/accounts":
        return {"data": list(PAGES)}
    raise AssertionError(path)


class R:
    headers = {}
    client = type('c', (), {'host': '9.9.9.9'})()


class Req:
    def __init__(self, t): self.headers = {'Authorization': f'Bearer {t}'}


async def run_login():
    r = await M.facebook_login_start(M.StartIn(base_url="https://api.x.com", return_url="https://app.x.com"), R())
    q = parse_qs(urlparse(r["url"]).query)
    assert "email" in q["scope"][0] and "pages_messaging" in q["scope"][0]
    resp = await M.facebook_callback(code="CODE", state=q["state"][0])
    loc = resp.headers["location"]
    if "/auth/facebook?code=" not in loc:
        return loc, None
    code = parse_qs(urlparse(loc).query)["code"][0]
    return loc, await M.facebook_login_finish(M.FinishIn(code=code))


async def main():
    M.graph = fake_graph
    created = []
    # 1) brand-new person with one Page -> shop created, named after the Page, Page waiting to connect
    ME.update(id=f"fb1{TAG}", name="Sok Dara", email=f"dara_{TAG}@gmail.com", picture={"data": {"url": "http://pic"}})
    PAGES[:] = [{"id": "PG1", "name": "Dara Cosmetics", "access_token": "PT1"}]
    loc, d = await run_login()
    u = await current_user(Req(d["token"])); created.append(u)
    biz = await db.businesses.find_one({"id": u["business_id"]})
    print("1 new:", d["new"], "| pending", d["pending_pages"], "| shop", biz["name"], "| role", u["role"], "| fb_uid", u.get("fb_uid") == ME["id"])
    print("  meta status pending", (await M.meta_status(u))["pending"])
    try:
        await M.facebook_login_finish(M.FinishIn(code=parse_qs(urlparse(loc).query)["code"][0])); print("  code reused (BAD)")
    except HTTPException as e:
        print("  reused code rejected", e.status_code)
    # 2) same person again (even if Facebook stops sharing email) -> same account
    ME.pop("email")
    loc, d2 = await run_login()
    u2 = await current_user(Req(d2["token"]))
    print("2 again: same user", u2["id"] == u["id"], "| new", d2["new"])
    # 3) unverified password account with that email -> Facebook proves ownership, password turned off
    em = f"victim_{TAG}@gmail.com"
    reg = await A.register(A.RegisterIn(email=em, password="attacker1", business_name="Squat"), R())
    old = reg["token"]
    ME.clear(); ME.update(id=f"fb3{TAG}", name="Real Owner", email=em); PAGES[:] = []
    loc, d3 = await run_login()
    u3 = await current_user(Req(d3["token"])); created.append(u3)
    try:
        await current_user(Req(old)); print("3 old session valid (BAD)")
    except HTTPException:
        print("3 claim: password_off", d3["password_off"], "| old session ended | no pages -> pending", d3["pending_pages"])
    # 4) Facebook account without email
    ME.clear(); ME.update(id=f"fb4{TAG}", name="No Mail"); PAGES[:] = [{"id": "PG4", "name": "No Mail Shop", "access_token": "PT4"}]
    loc, d4 = await run_login()
    u4 = await current_user(Req(d4["token"])); created.append(u4)
    print("4 no email:", u4["email"], "| shop", (await db.businesses.find_one({"id": u4["business_id"]}))["name"])
    # 5) removed teammate signs in with Facebook -> blocked with the reason
    owner_bid = u["business_id"]
    import billing as B
    await B.get_sub(db, owner_bid); await B.activate(db, owner_bid, "pro", 30, "test")
    await db.settings.update_one({"business_id": owner_bid}, {"$set": {"allowed_emails": [f"mate_{TAG}@gmail.com"]}})
    ME.clear(); ME.update(id=f"fb5{TAG}", name="Mate", email=f"mate_{TAG}@gmail.com"); PAGES[:] = []
    loc, d5 = await run_login()
    u5 = await current_user(Req(d5["token"])); created.append(u5)
    print("5 teammate joins:", u5["role"], u5["business_id"] == owner_bid)
    await db.settings.update_one({"business_id": owner_bid}, {"$set": {"allowed_emails": []}})
    loc, d6 = await run_login()
    print("6 removed teammate ->", loc.split("?")[0].endswith("/login"), parse_qs(urlparse(loc).query).get("fb_error"))
    # 7) user cancels on Facebook
    r = await M.facebook_login_start(M.StartIn(base_url="https://api.x.com", return_url="https://app.x.com"), R())
    st = parse_qs(urlparse(r["url"]).query)["state"][0]
    resp = await M.facebook_callback(error="access_denied", error_description="Permissions error", state=st)
    print("7 cancel ->", resp.headers["location"])
    # 8) page connect state for the new shop works with the normal Channels connect step
    print("8 pages for new shop", await M.facebook_pages(u))

    for x in created:
        await db.users.delete_many({"business_id": x["business_id"]})
        for c in ("settings", "subscriptions", "fb_choices"):
            await db[c].delete_many({"business_id": x["business_id"]})
        await db.businesses.delete_one({"id": x["business_id"]})
    await db.login_codes.delete_many({}); await db.oauth_states.delete_many({"purpose": "login"})

asyncio.run(main())
