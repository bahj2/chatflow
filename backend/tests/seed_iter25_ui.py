# seed/cleanup for iter25 UI check: one test shop with a pending KHR invoice and a paid USD invoice
import sys, uuid, requests
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
url = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL")][0]
DB = MongoClient("mongodb://localhost:27017")["replyflow"]
if sys.argv[1] == "seed":
    DB.rate_hits.delete_many({})
    email = f"test_i25ui_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{url}/api/auth/register", json={"email": email, "password": "secret123", "business_name": "TEST_i25ui"})
    bid = r.json()["user"]["business_id"]
    t = datetime.now(timezone.utc)
    base = {"business_id": bid, "item": "starter", "item_name": "Starter plan · 30 days", "md5": "0" * 32, "qr": "x", "deeplink": None, "created_at": t.isoformat()}
    DB.invoices.insert_many([
        {**base, "id": "TEST_i25_khr", "number": "RFTESTKHR", "amount": 41000.0, "currency": "KHR", "price_usd": 10.0, "status": "pending", "mode": "relay", "expires_at": (t + timedelta(minutes=10)).isoformat()},
        {**base, "id": "TEST_i25_usd", "number": "RFTESTUSD", "amount": 10.0, "currency": "USD", "price_usd": 10.0, "status": "expired", "mode": "local", "expires_at": (t - timedelta(minutes=10)).isoformat()},
    ])
    print(email, bid)
else:
    for u in DB.users.find({"email": {"$regex": "^test_i25ui_"}}):
        b = u["business_id"]
        for c in DB.list_collection_names():
            DB[c].delete_many({"business_id": b})
        DB.businesses.delete_one({"id": b})
    DB.invoices.delete_many({"id": {"$in": ["TEST_i25_khr", "TEST_i25_usd"]}})
    DB.rate_hits.delete_many({})
    print("cleaned", DB.users.count_documents({"email": {"$regex": "^test_i25ui_"}}))
