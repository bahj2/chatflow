from fastapi import APIRouter, Depends

import billing as B
from core import db, superadmin

router = APIRouter(prefix="/api")


@router.get("/admin/businesses")
async def admin_businesses(user=Depends(superadmin)):
    bizs = await db.businesses.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    convs = {d["_id"]: d["n"] async for d in db.conversations.aggregate([{"$group": {"_id": "$business_id", "n": {"$sum": 1}}}])}
    ai = {d["_id"]: d["n"] async for d in db.messages.aggregate([{"$match": {"role": "ai"}}, {"$group": {"_id": "$business_id", "n": {"$sum": 1}}}])}
    owners = {u["id"]: u["email"] async for u in db.users.find({"id": {"$in": [b["owner_id"] for b in bizs]}}, {"_id": 0, "id": 1, "email": 1})}
    tg = {d["business_id"] async for d in db.settings.find({"telegram_token": {"$ne": ""}}, {"_id": 0, "business_id": 1})}
    fb = {d["business_id"] async for d in db.settings.find({"fb_page_token": {"$ne": ""}}, {"_id": 0, "business_id": 1})}
    bill = await B.admin_rows(db, [b["id"] for b in bizs])
    empty = {"billing": None, "ai_cost_month": 0.0, "ai_calls_month": 0, "revenue": 0.0}
    return [{**b, "owner_email": owners.get(b["owner_id"]), "conversations": convs.get(b["id"], 0), "ai_replies": ai.get(b["id"], 0),
             "telegram": b["id"] in tg, "messenger": b["id"] in fb, **bill.get(b["id"], empty)} for b in bizs]
