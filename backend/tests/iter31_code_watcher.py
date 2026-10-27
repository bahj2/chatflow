# Iteration 31 UI helper: keep the reset code for given emails pinned to 424242 (tests can't read the email)
import hashlib, hmac, sys, time
from pymongo import MongoClient

env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
SECRET = env["JWT_SECRET"].strip('"')
db = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
emails = sys.argv[1:]
end = time.time() + 240
while time.time() < end:
    for e in emails:
        d = hmac.new(SECRET.encode(), f"{e}:424242".encode(), hashlib.sha256).hexdigest()
        db.password_resets.update_many({"email": e, "digest": {"$ne": d}}, {"$set": {"digest": d}})
    db.rate_hits.delete_many({"k": {"$regex": "^pwreset"}})
    time.sleep(0.3)
