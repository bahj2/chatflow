"""Smoke test: subscriptions, gating, KHQR invoices (admin confirm), quotas and AI cost tracking."""
import asyncio
import os
import sys
import time

import httpx

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from routers.webhooks import tg_secret  # noqa: E402

API = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0] + "/api"


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    stamp = str(int(time.time()))[-6:]
    async with httpx.AsyncClient(timeout=90) as h:
        adm = (await h.post(f"{API}/auth/login", json={"email": "admin@replyflow.com", "password": "admin123"})).json()
        A = {"Authorization": f"Bearer {adm['token']}"}
        r = (await h.post(f"{API}/auth/register", json={"email": f"bill-{stamp}@example.com", "password": "billtest123", "business_name": "Bill Shop"})).json()
        H, bid = {"Authorization": f"Bearer {r['token']}"}, r["user"]["business_id"]
        b = (await h.get(f"{API}/billing", headers=H)).json()
        print("trial", b["sub"]["plan"], b["sub"]["limit"], "pro", b["sub"]["pro"], "ready", b["payments_ready"])
        conv = {"message": {"chat": {"id": 777}, "from": {"first_name": "C"}, "text": "Hello, do you deliver?"}}
        tok = f"55{stamp}:TEST"
        await db.settings.update_one({"business_id": bid}, {"$set": {"telegram_token": tok}})
        hdr = {"X-Telegram-Bot-Api-Secret-Token": tg_secret(bid, tok)}
        await h.post(f"{API}/webhooks/telegram/{bid}", json=conv, headers=hdr)
        await asyncio.sleep(15)
        c = await db.conversations.find_one({"business_id": bid})
        print("trial reply roles", [m["role"] async for m in db.messages.find({"conversation_id": c["id"]}).sort("created_at", 1)])
        print("suggest", (await h.post(f"{API}/conversations/{c['id']}/suggest", headers=H)).status_code,
              "summary", (await h.post(f"{API}/conversations/{c['id']}/summary", headers=H)).status_code)
        cur = (await h.get(f"{API}/settings", headers=H)).json()
        print("team add", (await h.put(f"{API}/settings", headers=H, json={**cur, "allowed_emails": ["x@example.com"]})).status_code)
        print("checkout no bakong", (await h.post(f"{API}/billing/checkout", headers=H, json={"item": "starter"})).status_code)
        ap = (await h.get(f"{API}/settings", headers=A)).json()
        try:
            await flow(h, db, A, H, bid, c, conv, hdr, ap)
        finally:
            await h.put(f"{API}/settings", headers=A, json=ap)
            for coll in ("settings", "conversations", "messages", "subscriptions", "invoices", "ai_usage", "media"):
                await db[coll].delete_many({"business_id": bid})
            await db.businesses.delete_one({"id": bid})
            await db.users.delete_many({"business_id": bid})


async def flow(h, db, A, H, bid, c, conv, hdr, ap):
    if True:
        await h.put(f"{API}/settings", headers=A, json={**ap, "bakong_account_id": "replyflow@aclb", "bakong_merchant_name": "Replyflow AI"})
        print("topup on trial", (await h.post(f"{API}/billing/checkout", headers=H, json={"item": "topup"})).json())
        inv = (await h.post(f"{API}/billing/checkout", headers=H, json={"item": "starter"})).json()
        again = (await h.post(f"{API}/billing/checkout", headers=H, json={"item": "starter"})).json()
        print("invoice", inv["status"], inv["mode"], inv["amount"], "same", inv["id"] == again["id"], "qr", (await h.get(f"{API}/billing/invoices/{inv['id']}/qr.png")).status_code)
        print("pending list", len((await h.get(f"{API}/admin/invoices", headers=A)).json()) >= 1)
        s = (await h.post(f"{API}/admin/invoices/{inv['id']}/confirm", headers=A)).json()["sub"]
        print("after starter", s["plan"], s["limit"], s["days_left"], "used", s["used"])
        t = (await h.post(f"{API}/billing/checkout", headers=H, json={"item": "topup"})).json()
        s = (await h.post(f"{API}/admin/invoices/{t['id']}/confirm", headers=A)).json()["sub"]
        print("after topup extra", s["extra"])
        rn = (await h.post(f"{API}/billing/checkout", headers=H, json={"item": "starter"})).json()
        s = (await h.post(f"{API}/admin/invoices/{rn['id']}/confirm", headers=A)).json()["sub"]
        print("after renew days_left", s["days_left"], "used", s["used"])
        await db.subscriptions.update_one({"business_id": bid}, {"$set": {"used": 1000, "extra": 0}})
        conv["message"]["text"] = "What are your opening hours?"
        await h.post(f"{API}/webhooks/telegram/{bid}", json=conv, headers=hdr)
        await asyncio.sleep(8)
        print("used up -> roles", [m["role"] async for m in db.messages.find({"conversation_id": c["id"]}).sort("created_at", 1)][-2:],
              "reason", (await h.get(f"{API}/billing", headers=H)).json()["sub"]["reason"])
        await db.subscriptions.update_one({"business_id": bid}, {"$set": {"extra": 1}})
        conv["message"]["text"] = "Thanks! Where are you located?"
        await h.post(f"{API}/webhooks/telegram/{bid}", json=conv, headers=hdr)
        await asyncio.sleep(15)
        sub = await db.subscriptions.find_one({"business_id": bid})
        print("extra used", sub["extra"], sub["extra_used"], [m["role"] async for m in db.messages.find({"conversation_id": c["id"]}).sort("created_at", 1)][-2:])
        up = (await h.post(f"{API}/billing/checkout", headers=H, json={"item": "pro"})).json()
        s = (await h.post(f"{API}/admin/invoices/{up['id']}/confirm", headers=A)).json()["sub"]
        print("after pro", s["plan"], s["limit"], s["used"], "pro", s["pro"], "suggest", (await h.post(f"{API}/conversations/{c['id']}/suggest", headers=H)).status_code)
        u = await db.ai_usage.find_one({"business_id": bid})
        print("ai_usage", round(u["cost"], 6), u["calls"], u["input_tokens"], u["output_tokens"])
        row = [x for x in (await h.get(f"{API}/admin/businesses", headers=A)).json() if x["id"] == bid][0]
        print("admin row", row["billing"]["plan"], row["ai_cost_month"], row["revenue"])


asyncio.run(main())
