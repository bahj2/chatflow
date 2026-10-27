"""Seeds the demo shop used for the tutorial video (idempotent)."""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import httpx

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402

load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
import media as M  # noqa: E402
import payments as P  # noqa: E402

API = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0] + "/api"
EMAIL, PW, SHOP = "tour@replyflow.com", "TourDemo2026!", "Sokha Fashion"
U = "https://images.unsplash.com/"
PRODUCTS = [
    ("Air Runner Orange", "$45", "Shoes", 12, "photo-1600185365483-26d7a4cc7519", "White and orange running shoes, sizes 38-44, light and comfortable."),
    ("Street Sneaker", "$39", "Shoes", 2, "photo-1560769629-975ec94e6a86", "Colourful street sneakers, sizes 37-43."),
    ("Black Leather Bag", "$35", "Bags", 8, "photo-1705909237050-7a7625b47fac", "Black genuine leather handbag with two handles."),
    ("Grey Satchel", "$29", "Bags", 0, "photo-1605733513597-a8f8341084e6", "Grey satchel with gold buckles, fits a 13 inch laptop."),
    ("Denim Summer Set", "$25", "Clothes", None, "photo-1708523842501-800cd1c7505e", "Crop top, denim jacket and jeans set, sizes S-L."),
]
INFO = ("Sokha Fashion sells shoes, bags and clothes in Phnom Penh. Open every day 8:00-20:00. "
        "Delivery in Phnom Penh $1.5 (free over $50), provinces $2.5 by Virak Buntham. Exchange within 3 days.")


def iso(dt):
    return dt.isoformat()


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    async with httpx.AsyncClient(timeout=60) as h:
        r = await h.post(f"{API}/auth/login", json={"email": EMAIL, "password": PW})
        if r.status_code != 200:
            r = await h.post(f"{API}/auth/register", json={"email": EMAIL, "password": PW, "business_name": SHOP})
        r.raise_for_status()
        tok = r.json()["token"]
        auth = {"Authorization": f"Bearer {tok}"}
        me = (await h.get(f"{API}/auth/me", headers=auth)).json()
        bid = me["business_id"]
        await db.settings.update_one({"business_id": bid}, {"$set": {
            "business_name": SHOP, "business_type": "online shop", "business_info": INFO, "assistant_name": "Sreymom",
            "greeting": "សួស្តីបង! ខ្ញុំស្រីមុំ មកពី Sokha Fashion។ តើបងចង់រកទំនិញអ្វីដែរ?",
            "faqs": [{"q": "Do you deliver to provinces?", "a": "Yes, $2.5 by Virak Buntham, 1-2 days."}]}}, upsert=True)
        await db.products.delete_many({"business_id": bid})
        prods = []
        for name, price, cat, stock, img, desc in PRODUCTS:
            data = (await h.get(f"{U}{img}?w=700&q=80&fm=jpg")).content
            mid = (await M.save_media(db, bid, data, "image/jpeg", "product"))["id"]
            p = (await h.post(f"{API}/products", headers=auth, json={"name": name, "price": price, "category": cat, "stock": stock,
                                                                       "description": desc, "image_media_id": mid})).json()
            prods.append(p)
    await db.conversations.delete_many({"business_id": bid})
    await db.messages.delete_many({"business_id": bid})
    await db.orders.delete_many({"business_id": bid})
    now = datetime.now(timezone.utc)
    chats = [
        ("Dara", "telegram", [("user", "សួស្តីបង មានស្បែកជើងប្រុសលេខ 42 ទេ?"), ("ai", "មានបង 😊 Air Runner Orange តម្លៃ $45 មានលេខ 38-44។ បងចង់យកមួយគូទេ?", 0),
                              ("user", "យក ១ គូ"), ("ai", "អរគុណបង! សរុប $45។ សូមស្កេន KHQR ខាងក្រោមដោយកម្មវិធីធនាគារណាមួយ។", "khqr")]),
        ("Sreyneang", "telegram", [("user", "កាបូបខ្មៅនៅមានទេបង?"), ("ai", "នៅមានបង! Black Leather Bag តម្លៃ $35 ស្បែកពិតប្រាកដ។", 2)]),
        ("Vannak", "messenger", [("user", "Do you deliver to Siem Reap?"), ("ai", "Yes! Delivery to provinces is $2.5 by Virak Buntham, 1-2 days.")]),
    ]
    for ci, (name, ch, msgs) in enumerate(chats):
        cid, t0 = str(uuid.uuid4()), now - timedelta(minutes=40 * (ci + 1))
        last = msgs[-1]
        for mi, m in enumerate(msgs):
            atts = []
            if len(m) > 2 and isinstance(m[2], int):
                atts = [{"type": "product", "product_id": prods[m[2]]["id"], "media_id": prods[m[2]]["image_media_id"], "name": prods[m[2]]["name"], "price": prods[m[2]]["price"]}]
            elif len(m) > 2 and m[2] == "khqr":
                qr, md5 = P._local_qr("sokha_fashion@aclb", SHOP, "Phnom Penh", 45.0, "USD", "RF-7A21C9D0")
                media = await M.save_media(db, bid, P._png(qr), "image/png", "khqr")
                oid = str(uuid.uuid4())
                await db.orders.insert_one({"id": oid, "business_id": bid, "conversation_id": cid, "channel": ch, "customer": name, "number": "RF-7A21C9D0",
                                            "items": [{"product_id": prods[0]["id"], "name": prods[0]["name"], "price": "$45", "unit": 45.0, "qty": 1, "total": 45.0}],
                                            "total": 45.0, "currency": "USD", "mode": "local", "price_total": None, "price_currency": None, "qr": qr, "md5": md5,
                                            "deeplink": None, "qr_media_id": media["id"], "status": "paid", "created_at": iso(t0), "expires_at": iso(t0 + timedelta(minutes=10)),
                                            "paid_at": iso(t0 + timedelta(minutes=3)), "paid_by": "auto", "updated_at": iso(t0)})
                atts = [{"type": "khqr", "order_id": oid, "media_id": media["id"], "number": "RF-7A21C9D0", "total": 45.0, "currency": "USD", "amount_text": "$45.00",
                         "expires_at": iso(t0 + timedelta(minutes=10)), "status": "paid", "deeplink": None}]
            await db.messages.insert_one({"id": str(uuid.uuid4()), "conversation_id": cid, "business_id": bid, "role": m[0], "text": m[1],
                                          "attachments": atts, "created_at": iso(t0 + timedelta(seconds=30 * mi))})
        await db.conversations.insert_one({"id": cid, "business_id": bid, "channel": ch, "external_id": f"demo-{ci}", "name": name, "ai_enabled": True,
                                           "unread": 1 if ci == 1 else 0, "last_message": last[1], "last_role": last[0], "created_at": iso(t0),
                                           "updated_at": iso(t0 + timedelta(seconds=30 * len(msgs)))})
    print("seeded", bid)


asyncio.run(main())
