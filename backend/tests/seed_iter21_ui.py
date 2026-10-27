"""Seed/cleanup for iter21 UI test: `python seed_iter21_ui.py seed|cleanup`. Seed creates a trial shop + 1 conversation and sets admin Bakong."""
import json
import os
import sys
import uuid

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
STATE = "/tmp/iter21_ui.json"
COLLS = ("settings", "conversations", "messages", "subscriptions", "invoices", "ai_usage", "media", "products", "orders", "notion_links", "notion_docs")


def admin_h():
    t = requests.post(f"{API}/auth/login", json={"email": "admin@replyflow.com", "password": "admin123"}).json()["token"]
    return {"Authorization": f"Bearer {t}"}


if sys.argv[1] == "seed":
    tag = uuid.uuid4().hex[:6]
    email = f"test_ui21_{tag}@example.com"
    d = requests.post(f"{API}/auth/register", json={"email": email, "password": "test12345", "business_name": "TEST_UI21 Shop"}).json()
    bid = d["user"]["business_id"]
    cid, t = str(uuid.uuid4()), "2026-01-10T10:00:00+00:00"
    DB.conversations.insert_one({"id": cid, "business_id": bid, "channel": "telegram", "external_id": f"ui{tag}", "name": "TEST Dara",
                                 "ai_enabled": True, "unread": 1, "last_message": "Do you deliver?", "created_at": t, "updated_at": t})
    DB.messages.insert_one({"id": str(uuid.uuid4()), "conversation_id": cid, "business_id": bid, "role": "user",
                            "text": "Hi! Do you deliver to Siem Reap? How much is iced coffee?", "attachments": [], "created_at": t})
    A = admin_h()
    orig = requests.get(f"{API}/settings", headers=A).json()
    r = requests.put(f"{API}/settings", headers=A, json={**orig, "bakong_account_id": "replyflow@aclb", "bakong_merchant_name": "Replyflow AI"})
    json.dump({"email": email, "bid": bid, "cid": cid, "orig": orig}, open(STATE, "w"))
    print("seeded", email, bid, cid, "admin bakong put", r.status_code)
elif sys.argv[1] == "cleanup":
    st = json.load(open(STATE))
    A = admin_h()
    print("restore admin", requests.put(f"{API}/settings", headers=A, json=st["orig"]).status_code)
    for c in COLLS:
        DB[c].delete_many({"business_id": st["bid"]})
    DB.businesses.delete_one({"id": st["bid"]})
    DB.users.delete_many({"business_id": st["bid"]})
    print("cleaned", st["bid"])
