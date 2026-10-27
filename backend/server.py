import asyncio
import os
import uuid

from fastapi import FastAPI
from pymongo.errors import OperationFailure
from starlette.middleware.cors import CORSMiddleware

from core import client, db, logger, now_iso, hash_pw, verify_pw, Settings
import media as M
from orders import payments_loop
from routers import admin, auth, channels, inbox, notion, settings, shop, subscriptions, voice, webhooks

app = FastAPI()
for r in (auth, admin, settings, webhooks, inbox, shop, voice, notion, channels, subscriptions):
    app.include_router(r.router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    try:
        await db.conversations.drop_index("channel_1_external_id_1")
    except OperationFailure:
        pass
    await db.conversations.create_index([("business_id", 1), ("channel", 1), ("external_id", 1)], unique=True)
    await db.conversations.create_index([("business_id", 1), ("updated_at", -1)])
    await db.conversations.create_index("id", unique=True)
    await db.messages.create_index([("conversation_id", 1), ("created_at", -1)])
    await db.messages.create_index([("business_id", 1), ("role", 1)])
    await db.businesses.create_index("id", unique=True)
    await db.settings.create_index("business_id", unique=True, partialFilterExpression={"business_id": {"$exists": True}})
    await db.users.create_index("id", unique=True)
    await db.products.create_index([("business_id", 1), ("is_deleted", 1), ("created_at", -1)])
    await db.media.create_index("id", unique=True)
    await db.notion_links.create_index("business_id", unique=True)
    await db.notion_docs.create_index([("business_id", 1), ("notion_id", 1)], unique=True)
    await db.cron_runs.create_index("id", unique=True)
    await db.cron_runs.create_index("created", expireAfterSeconds=7 * 86400)
    await db.orders.create_index("id", unique=True)
    await db.orders.create_index([("business_id", 1), ("created_at", -1)])
    await db.orders.create_index([("business_id", 1), ("number", 1)], unique=True)
    await db.orders.create_index([("status", 1), ("mode", 1), ("expires_at", 1)])
    await db.messages.create_index("attachments.order_id", sparse=True)
    await db.subscriptions.create_index("business_id", unique=True)
    await db.invoices.create_index("id", unique=True)
    await db.invoices.create_index([("business_id", 1), ("created_at", -1)])
    await db.invoices.create_index([("status", 1), ("expires_at", 1)])
    await db.ai_usage.create_index([("business_id", 1), ("month", 1)], unique=True)
    app.state.payments_task = asyncio.create_task(payments_loop())
    try:
        M.init_storage()
    except Exception as e:
        logger.error("Storage init failed: %s", e)
    email, pw = os.environ['ADMIN_EMAIL'].lower(), os.environ['ADMIN_PASSWORD']
    existing = await db.users.find_one({"email": email})
    if not existing:
        existing = {"id": str(uuid.uuid4()), "email": email, "password_hash": hash_pw(pw), "name": "Admin", "role": "superadmin", "created_at": now_iso()}
        await db.users.insert_one(dict(existing))
    elif not existing.get("password_hash") or not verify_pw(pw, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_pw(pw)}})
    await db.users.update_one({"email": email}, {"$set": {"role": "superadmin"}})
    if not existing.get("business_id"):
        await migrate_single_tenant(existing)


async def migrate_single_tenant(admin: dict):
    bid = str(uuid.uuid4())
    old = await db.settings.find_one({"key": "main"}, {"_id": 0, "key": 0})
    await db.businesses.insert_one({"id": bid, "name": (old or {}).get("business_name", "My Business"), "owner_id": admin["id"], "created_at": now_iso()})
    if old:
        await db.settings.update_one({"key": "main"}, {"$set": {"business_id": bid}, "$unset": {"key": ""}})
    else:
        await db.settings.insert_one({"business_id": bid, **Settings().model_dump()})
    missing = {"business_id": {"$exists": False}}
    for coll in (db.users, db.conversations, db.messages):
        await coll.update_many(missing, {"$set": {"business_id": bid}})
    logger.info("Migrated single-tenant data to business %s", bid)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
