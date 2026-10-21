# cleanup after iteration 12: delete seller voice (admin + loadtest), auto_reply true, remove TEST_ convs + my embed convs
import os, requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from dotenv import dotenv_values

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
for em, pw in [("admin@replyflow.com", "admin123"), ("loadtest+706ab4fd@example.com", "loadtest123")]:
    t = requests.post(f"{API}/auth/login", json={"email": em, "password": pw}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    print(em, requests.delete(f"{API}/settings/seller-voice", headers=h).status_code)
    s = requests.get(f"{API}/settings", headers=h).json()
    print(" media", repr(s["seller_voice_media_id"]), "auto_reply", s["auto_reply"])

env = dotenv_values("/app/backend/.env")
db = MongoClient(env["MONGO_URL"])[env["DB_NAME"]]
since = (datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat()
q = {"$or": [{"external_id": {"$regex": "^TEST_"}}, {"channel": "web", "created_at": {"$gte": since}}]}
convs = list(db.conversations.find(q, {"_id": 0, "id": 1, "name": 1, "external_id": 1, "channel": 1}))
print(convs)
ids = [c["id"] for c in convs]
print("msgs", db.messages.delete_many({"conversation_id": {"$in": ids}}).deleted_count,
      "convs", db.conversations.delete_many({"id": {"$in": ids}}).deleted_count)
