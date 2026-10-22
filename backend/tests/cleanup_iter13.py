# Iteration 13 cleanup: delete loadtest products + TEST_ web conversations/messages in loadtest business
import asyncio, os, requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
load_dotenv("/app/backend/.env")
API = "https://chatflow-pilot.preview.emergentagent.com/api"
r = requests.post(f"{API}/auth/login", json={"email": "loadtest+706ab4fd@example.com", "password": "loadtest123"}).json()
h, bid = {"Authorization": "Bearer " + r["token"]}, r["user"]["business_id"]
for p in requests.get(f"{API}/products", headers=h).json():
    print("del product", p["name"], requests.delete(f"{API}/products/{p['id']}", headers=h).status_code)
async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    convs = await db.conversations.find({"business_id": bid, "external_id": {"$regex": "^TEST_"}}, {"_id": 0, "id": 1}).to_list(1000)
    ids = [c["id"] for c in convs]
    m = await db.messages.delete_many({"conversation_id": {"$in": ids}})
    c = await db.conversations.delete_many({"id": {"$in": ids}})
    print("deleted convs", c.deleted_count, "msgs", m.deleted_count)
    # embed UI session conversation (non TEST_ session id) from playwright run
    ui = await db.conversations.find({"business_id": bid, "channel": "web", "last_message": {"$regex": "CapCut|premium", "$options": "i"}}, {"_id": 0, "id": 1, "external_id": 1}).to_list(50)
    print("ui convs", ui)
    for u in ui:
        await db.messages.delete_many({"conversation_id": u["id"]}); await db.conversations.delete_one({"id": u["id"]})
asyncio.run(main())
