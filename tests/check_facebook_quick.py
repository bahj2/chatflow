"""Instant Connect (remembered Facebook approval). Graph API STUBBED (MOCKED)."""
import asyncio, os, sys, uuid
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv; load_dotenv('/app/backend/.env')
os.environ.update(META_APP_ID='111', META_APP_SECRET='platform-secret', META_WEBHOOK_VERIFY_TOKEN='vt-123')
import routers.meta as M
from routers.auth import create_business
from core import db, get_settings

PAGES, REVOKED = [], {"v": False}


async def fake_graph(method, path, **p):
    if path == "me/accounts":
        if REVOKED["v"]:
            raise M.GraphError("Error validating access token")
        return {"data": list(PAGES)}
    if path.endswith("/subscribed_apps"):
        return {"success": True}
    raise AssertionError(path)


async def main():
    M.graph = fake_graph
    uid = str(uuid.uuid4()); bid = await create_business("Quick Shop", uid)
    user = {"id": uid, "business_id": bid, "role": "owner", "email": f"q_{uid[:6]}@x.com"}
    await db.users.insert_one(dict(user))
    body = M.StartIn(base_url="https://api.x.com", return_url="https://app.x.com")

    r = await M.facebook_quick(body, user); print("no approval yet -> facebook:", "url" in r)
    await M.remember_token(uid, "USER_TOKEN")
    PAGES[:] = [{"id": "Q1", "name": "Quick Page", "access_token": "PTQ1"}]
    r = await M.facebook_quick(body, user); print("one page -> instant:", r.get("connected"), r.get("page_name"))
    s = await get_settings(bid); print("  saved", s.fb_oauth, s.fb_page_id, s.fb_page_token)
    await M.facebook_disconnect(user)
    PAGES[:] = [{"id": "Q1", "name": "Quick Page", "access_token": "PTQ1"}, {"id": "Q2", "name": "Second", "access_token": "PTQ2"}]
    r = await M.facebook_quick(body, user); print("two pages -> picker:", r, [p["name"] for p in await M.facebook_pages(user)])
    REVOKED["v"] = True
    r = await M.facebook_quick(body, user)
    u = await db.users.find_one({"id": uid})
    print("approval revoked -> facebook:", "url" in r, "| stale key cleared", "fb_user_token_enc" not in u)

    await db.users.delete_one({"id": uid})
    for c in ("settings", "subscriptions", "fb_choices", "oauth_states"):
        await db[c].delete_many({"business_id": bid})
    await db.businesses.delete_one({"id": bid})

asyncio.run(main())
