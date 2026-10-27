# Iter26 UI seed: shop owner with one KHR invoice (41000, price_usd 10) and one USD invoice ($10). Run with "clean" to remove.
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
API = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
EMAIL = "test_i26ui@example.com"

if len(sys.argv) > 1 and sys.argv[1] == "clean":
    u = DB.users.find_one({"email": EMAIL})
    if u:
        bid = u["business_id"]
        for c in ("settings", "subscriptions", "invoices", "media", "ai_usage", "conversations", "messages", "products", "orders"):
            DB[c].delete_many({"business_id": bid})
        DB.businesses.delete_one({"id": bid})
        DB.users.delete_many({"business_id": bid})
    print("cleaned")
    sys.exit()

DB.rate_hits.delete_many({})
r = requests.post(f"{API}/auth/register", json={"email": EMAIL, "password": "test12345", "business_name": "TEST_i26ui"})
if r.status_code != 200:
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": "test12345"})
bid = r.json()["user"]["business_id"]
now = datetime.now(timezone.utc)
base = {"business_id": bid, "status": "pending", "mode": "relay", "md5": "x", "qr": "x", "item": "starter",
        "item_name": "Starter plan · 30 days", "created_at": now.isoformat(), "expires_at": (now + timedelta(minutes=10)).isoformat()}
DB.invoices.delete_many({"business_id": bid})
DB.invoices.insert_one({**base, "id": "TEST_inv_khr", "number": "RFTEST1", "amount": 41000, "currency": "KHR", "price_usd": 10})
DB.invoices.insert_one({**base, "id": "TEST_inv_usd", "number": "RFTEST2", "amount": 10, "currency": "USD", "price_usd": 10,
                        "created_at": (now - timedelta(minutes=1)).isoformat()})
print("seeded", bid)
