import asyncio
import json
import random
import statistics
import time
import uuid
from datetime import datetime, timezone, timedelta

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

API = "http://localhost:8001/api"
QUESTIONS = [
    "Hi, how much is a cappuccino?", "Do you deliver to the city centre?", "What time do you open on Sunday?",
    "Can I book a table for 6 people tomorrow at 7pm?", "Do you have oat milk?", "Is there wifi?",
    "Привет! Сколько стоит латте?", "Bonjour, vous avez des croissants sans gluten?", "Hola, ¿tienen terraza?",
    "My order arrived cold, what can you do?", "Do you sell coffee beans to take home?", "Can I pay by card?",
]
INFO = ("Sunrise Coffee — specialty coffee shop at 12 Market Street. Cappuccino $3.50, latte $3.80, espresso $2.50. "
        "Oat and almond milk +$0.50. Open Mon-Sat 7:00-20:00, Sun 9:00-17:00. Free delivery within 3 km for orders over $15. "
        "Card and cash accepted. Free wifi. Table bookings for up to 8 people by chat. Gluten-free pastries available.")


async def chat(h, bid, i):
    t0 = time.perf_counter()
    try:
        r = await h.post(f"{API}/public/{bid}/chat", json={"session_id": f"load-{uuid.uuid4()}", "text": random.choice(QUESTIONS), "name": f"Load customer {i+1}"},
                         headers={"X-Forwarded-For": f"10.9.{i // 256}.{i % 256}"})
        ok = r.status_code == 200 and (r.json().get("reply") or {}).get("text")
        return {"ok": bool(ok), "status": r.status_code, "secs": time.perf_counter() - t0}
    except Exception as e:
        return {"ok": False, "status": str(e)[:80], "secs": time.perf_counter() - t0}


async def register(h, name):
    r = await h.post(f"{API}/auth/register", json={"email": f"loadtest+{uuid.uuid4().hex[:8]}@example.com", "password": "loadtest123", "business_name": name},
                     headers={"X-Forwarded-For": f"10.8.{random.randint(0, 255)}.{random.randint(0, 255)}"})
    r.raise_for_status()
    d = r.json()
    return d["user"]["business_id"], {"Authorization": f"Bearer {d['token']}"}


async def main():
    out = {}
    async with httpx.AsyncClient(timeout=120) as h:
        bid, H = await register(h, "Load Test — Sunrise Coffee")
        s = (await h.get(f"{API}/settings", headers=H)).json()
        s.update(business_info=INFO, business_type="services")
        await h.put(f"{API}/settings", json=s, headers=H)

        t0 = time.perf_counter()
        res = await asyncio.gather(*[chat(h, bid, i) for i in range(100)])
        wall = time.perf_counter() - t0
        secs = sorted(r["secs"] for r in res if r["ok"])
        out["chat_100"] = {
            "business_id": bid, "sent": 100, "ai_replied": sum(r["ok"] for r in res), "wall_seconds": round(wall, 1),
            "p50": round(statistics.median(secs), 1) if secs else None, "p95": round(secs[int(len(secs) * 0.95) - 1], 1) if secs else None,
            "slowest": round(secs[-1], 1) if secs else None, "fastest": round(secs[0], 1) if secs else None,
            "errors": [r["status"] for r in res if not r["ok"]][:10],
        }
        inbox = (await h.get(f"{API}/conversations", headers=H)).json()
        stats = (await h.get(f"{API}/stats", headers=H)).json()
        out["chat_100"]["inbox_total"] = inbox["total"]
        out["chat_100"]["ai_replies_in_db"] = stats["ai_replies"]

        # big inbox: 3,000 conversations seeded directly
        big_bid, BH = await register(h, "Load Test — Big Inbox (3,000 chats)")
        import os
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        now = datetime.now(timezone.utc)
        convs, msgs = [], []
        for i in range(3000):
            ts = (now - timedelta(minutes=i * 7)).isoformat()
            cid = str(uuid.uuid4())
            ch = ("web", "telegram", "messenger")[i % 3]
            q = random.choice(QUESTIONS)
            convs.append({"id": cid, "business_id": big_bid, "channel": ch, "external_id": f"seed-{i}", "name": f"Customer #{3000 - i}",
                          "ai_enabled": True, "unread": 1 if i % 4 == 0 else 0, "last_message": q, "created_at": ts, "updated_at": ts, "last_role": "user"})
            msgs.append({"id": str(uuid.uuid4()), "conversation_id": cid, "business_id": big_bid, "role": "user", "text": q, "created_at": ts})
        await db.conversations.insert_many(convs)
        await db.messages.insert_many(msgs)

        async def timed(params):
            t = time.perf_counter()
            d = (await h.get(f"{API}/conversations", headers=BH, params=params)).json()
            return round((time.perf_counter() - t) * 1000), d

        ms1, p1 = await timed({})
        pages, cursor, seen, ms_all = 1, p1["items"][-1]["updated_at"], len(p1["items"]), []
        while True:
            ms, d = await timed({"before": cursor})
            ms_all.append(ms)
            seen += len(d["items"])
            pages += 1
            if not d["has_more"]:
                break
            cursor = d["items"][-1]["updated_at"]
        ms_s, ds = await timed({"q": "cappuccino"})
        ms_f, df = await timed({"channel": "telegram"})
        out["big_inbox"] = {"business_id": big_bid, "seeded": 3000, "total_reported": p1["total"], "paged_through": seen, "pages": pages,
                            "first_page_ms": ms1, "avg_page_ms": round(sum(ms_all) / len(ms_all)), "search_ms": ms_s, "search_hits": ds["total"],
                            "telegram_filter_ms": ms_f, "telegram_total": df["total"]}
    print(json.dumps(out, indent=2))
    json.dump(out, open("/app/test_reports/load_test_100.json", "w"), indent=2)


asyncio.run(main())
