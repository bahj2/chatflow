"""One-off: permanently delete all website-chat conversations (channel 'web') with their messages, orders and media records."""
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    convs = [c["id"] async for c in db.conversations.find({"channel": "web"}, {"_id": 0, "id": 1})]
    media = set()
    async for m in db.messages.find({"conversation_id": {"$in": convs}}, {"_id": 0, "attachments": 1}):
        for a in m.get("attachments") or []:
            if a.get("type") in ("audio", "khqr") and a.get("media_id"):
                media.add(a["media_id"])
    orders = db.orders.find({"$or": [{"channel": "web"}, {"conversation_id": {"$in": convs}}]}, {"_id": 0, "qr_media_id": 1})
    media |= {o["qr_media_id"] async for o in orders if o.get("qr_media_id")}
    print("conversations:", (await db.conversations.delete_many({"id": {"$in": convs}})).deleted_count)
    print("messages:", (await db.messages.delete_many({"conversation_id": {"$in": convs}})).deleted_count)
    print("orders:", (await db.orders.delete_many({"$or": [{"channel": "web"}, {"conversation_id": {"$in": convs}}]})).deleted_count)
    print("media records:", (await db.media.delete_many({"id": {"$in": list(media)}})).deleted_count)
    await db.settings.update_many({}, {"$unset": {"greeting": ""}})


asyncio.run(main())
