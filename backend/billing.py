"""Shop subscriptions: plans, monthly AI-reply quotas, real AI cost tracking and KHQR invoices paid to the platform's Bakong account."""
import math
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

import payments as P

PLANS = {
    "trial": {"name": "Free trial", "price": 0, "replies": 200, "days": 14, "team": 1, "pro": False},
    "starter": {"name": "Starter", "price": 10, "replies": 1000, "days": 30, "team": 1, "pro": False},
    "pro": {"name": "Pro", "price": 25, "replies": 3000, "days": 30, "team": 3, "pro": True},
    "business": {"name": "Business", "price": 59, "replies": 8000, "days": 30, "team": 10, "pro": True},
}
PAID = ("starter", "pro", "business")
TOPUP = {"replies": 1000, "price": 5}
PRICE_PER_M = {"gpt-6-luna": (0.10, 0.50), "claude-sonnet-4-5-20250929": (3.0, 15.0), "gemini-3-flash-preview": (0.50, 3.0)}  # USD per 1M tokens (in, out)
STT_PER_MIN = 0.006
PRO_ONLY = "This is a Pro feature. Upgrade in Billing to use it."


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(d: datetime) -> str:
    return d.isoformat()


def month() -> str:
    return now().strftime("%Y-%m")


# ---------- Subscriptions ----------
async def get_sub(db, bid: str) -> dict:
    sub = await db.subscriptions.find_one({"business_id": bid}, {"_id": 0})
    if not sub:
        t = now()
        end = iso(t + timedelta(days=PLANS["trial"]["days"]))
        sub = {"business_id": bid, "plan": "trial", "period_start": iso(t), "period_end": end, "paid_until": end,
               "used": 0, "limit": PLANS["trial"]["replies"], "extra": 0, "extra_used": 0, "created_at": iso(t),
               "exempt": bool(await db.users.find_one({"business_id": bid, "role": "superadmin"}, {"_id": 1}))}
        try:
            await db.subscriptions.insert_one(dict(sub))
        except DuplicateKeyError:
            sub = await db.subscriptions.find_one({"business_id": bid}, {"_id": 0})
    return await roll(db, sub)


async def roll(db, sub: dict) -> dict:
    """Starts the next 30-day reply window when a paid plan runs longer than the current one."""
    t, end = now(), datetime.fromisoformat(sub["period_end"])
    paid = datetime.fromisoformat(sub["paid_until"])
    if end > t or paid <= end:
        return sub
    while end <= t and end < paid:
        start, end = end, min(end + timedelta(days=30), paid)
    upd = {"period_start": iso(start), "period_end": iso(end), "used": 0}
    await db.subscriptions.update_one({"business_id": sub["business_id"], "period_end": sub["period_end"]}, {"$set": upd})
    return {**sub, **upd}


def view(sub: dict) -> dict:
    plan, t = PLANS[sub["plan"]], now()
    paid = datetime.fromisoformat(sub["paid_until"])
    active = sub["exempt"] or paid > t
    reason = "" if sub["exempt"] else "ended" if not active else "used_up" if sub["used"] >= sub["limit"] and sub["extra"] <= 0 else ""
    return {"plan": sub["plan"], "plan_name": plan["name"], "price": plan["price"], "period_start": sub["period_start"],
            "period_end": sub["period_end"], "paid_until": sub["paid_until"], "days_left": max(0, math.ceil((paid - t).total_seconds() / 86400)),
            "used": sub["used"], "limit": sub["limit"], "extra": sub["extra"], "extra_used": sub.get("extra_used", 0), "active": active,
            "paused": bool(reason), "reason": reason, "pro": sub["exempt"] or (plan["pro"] and active),
            "team": 1000 if sub["exempt"] else plan["team"], "exempt": sub["exempt"]}


async def sub_status(db, bid: str) -> dict:
    return view(await get_sub(db, bid))


def effective(s, v: dict):
    """Settings with Pro-only extras (voice replies, seller voice clone) switched off for shops without Pro."""
    return s if v["pro"] else s.model_copy(update={"voice_replies": False, "seller_voice_media_id": "", "seller_voice_text": ""})


def auto_confirm(ps) -> bool:
    return bool(ps) and (ps.khqr_token or "").strip().startswith(P.RELAY_PREFIX)


async def reserve(db, bid: str) -> str:
    """Takes one AI reply from the plan, then from top-ups; '' means AI replies are paused."""
    sub = await get_sub(db, bid)
    if sub["exempt"]:
        return "exempt"
    base = {"business_id": bid, "paid_until": {"$gt": iso(now())}}
    if (await db.subscriptions.update_one({**base, "$expr": {"$lt": ["$used", "$limit"]}}, {"$inc": {"used": 1}})).modified_count:
        return "plan"
    if (await db.subscriptions.update_one({**base, "extra": {"$gt": 0}}, {"$inc": {"extra": -1, "extra_used": 1}})).modified_count:
        return "extra"
    return ""


async def refund(db, bid: str, kind: str):
    inc = {"plan": {"used": -1}, "extra": {"extra": 1, "extra_used": -1}}.get(kind)
    if inc:
        await db.subscriptions.update_one({"business_id": bid}, {"$inc": inc})


# ---------- AI cost tracking ----------
async def record(db, bid: str, kind: str, model: str, usage):
    if not bid or not usage:
        return
    pin, pout = PRICE_PER_M.get(model, (0.0, 0.0))
    cost = (usage.input_tokens * pin + usage.output_tokens * pout) / 1e6
    await db.ai_usage.update_one({"business_id": bid, "month": month()},
                                 {"$inc": {"cost": cost, "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens, f"calls.{kind}": 1}}, upsert=True)


async def record_stt(db, bid: str, seconds: float):
    await db.ai_usage.update_one({"business_id": bid, "month": month()},
                                 {"$inc": {"cost": seconds / 60 * STT_PER_MIN, "stt_seconds": seconds, "calls.stt": 1}}, upsert=True)


# ---------- Invoices (KHQR to the platform owner's Bakong account) ----------
INV_FIELDS = ("id", "number", "item", "item_name", "amount", "currency", "status", "mode", "deeplink", "created_at", "expires_at", "paid_at")


def inv_view(i: dict) -> dict:
    return {k: i.get(k) for k in INV_FIELDS}


async def checkout(db, bid: str, item: str, ps) -> dict:
    sub = view(await get_sub(db, bid))
    if sub["exempt"]:
        raise HTTPException(400, "The platform account is never billed.")
    if item == "topup":
        if sub["plan"] not in PAID or not sub["active"]:
            raise HTTPException(400, "Extra replies need an active paid plan. Choose a plan first.")
        amount, name = TOPUP["price"], f"+{TOPUP['replies']:,} AI replies"
    elif item in PAID:
        amount, name = PLANS[item]["price"], f"{PLANS[item]['name']} plan · 30 days"
    else:
        raise HTTPException(400, "Unknown plan")
    if not (ps and P.enabled(ps)):
        raise HTTPException(503, "Online payment isn't set up yet. Please contact Replyflow AI to pay.")
    soon = iso(now() + timedelta(minutes=1))
    old = await db.invoices.find_one({"business_id": bid, "item": item, "status": "pending", "expires_at": {"$gt": soon}}, {"_id": 0})
    if old:
        return inv_view(old)
    number = "RF" + uuid.uuid4().hex[:8].upper()
    try:
        qr = await P.make_qr(ps, float(amount), "USD", number)
    except P.PaymentError as e:
        raise HTTPException(503, f"Payment QR could not be created: {e}")
    t = now()
    inv = {"id": str(uuid.uuid4()), "number": number, "business_id": bid, "item": item, "item_name": name, "amount": float(amount),
           "currency": "USD", "status": "pending", "mode": qr["mode"], "md5": qr["md5"], "qr": qr["qr"], "deeplink": qr["deeplink"],
           "created_at": iso(t), "expires_at": iso(t + timedelta(minutes=P.QR_MINUTES))}
    await db.invoices.insert_one(dict(inv))
    return inv_view(inv)


async def settle(db, inv: dict, by: str) -> bool:
    t = now()
    if not (await db.invoices.update_one({"id": inv["id"], "status": {"$ne": "paid"}}, {"$set": {"status": "paid", "paid_at": iso(t), "paid_by": by}})).modified_count:
        return False
    bid = inv["business_id"]
    if inv["item"] == "topup":
        await db.subscriptions.update_one({"business_id": bid}, {"$inc": {"extra": TOPUP["replies"]}})
        return True
    await activate(db, bid, inv["item"], 30, by)
    return True


async def activate(db, bid: str, item: str, days: int, by: str):
    """Same plan still running: adds the days (next reply window starts when this one ends). Otherwise starts the plan now."""
    t, sub, plan = now(), await get_sub(db, bid), PLANS[item]
    paid = datetime.fromisoformat(sub["paid_until"])
    if sub["plan"] == item and paid > t:
        upd = {"paid_until": iso(paid + timedelta(days=days))}
    else:
        upd = {"plan": item, "period_start": iso(t), "period_end": iso(t + timedelta(days=min(30, days))),
               "paid_until": iso(t + timedelta(days=days)), "used": 0, "limit": plan["replies"]}
    await db.subscriptions.update_one({"business_id": bid}, {"$set": {**upd, "activated_by": by, "activated_at": iso(t)}})


async def poll(db, ps):
    """Expires unpaid invoices and, with a KHQR.dev token, settles paid ones automatically (late payments within a day too)."""
    await db.invoices.update_many({"status": "pending", "expires_at": {"$lt": iso(now())}}, {"$set": {"status": "expired"}})
    token = (getattr(ps, "khqr_token", "") or "").strip()
    if not token.startswith(P.RELAY_PREFIX):
        return
    flt = {"mode": "relay", "status": {"$in": ["pending", "expired"]}, "created_at": {"$gt": iso(now() - timedelta(days=1))}}
    invs = await db.invoices.find(flt, {"_id": 0}).to_list(500)
    for i in range(0, len(invs), 50):
        chunk = invs[i:i + 50]
        paid = set(await P.bulk_paid(token, [x["md5"] for x in chunk]))
        for inv in chunk:
            if inv["md5"] in paid:
                await settle(db, inv, "auto")


async def admin_rows(db, all_bids: list) -> dict:
    subs = {s["business_id"]: view(await roll(db, s)) async for s in db.subscriptions.find({}, {"_id": 0})}
    for b in all_bids:
        if b not in subs:
            subs[b] = view(await get_sub(db, b))  # older shops: their trial starts now, as it would on their next message
    cost = {u["business_id"]: u for u in await db.ai_usage.find({"month": month()}, {"_id": 0}).to_list(10000)}
    revenue = {d["_id"]: d["total"] async for d in db.invoices.aggregate([{"$match": {"status": "paid"}}, {"$group": {"_id": "$business_id", "total": {"$sum": "$amount"}}}])}
    bids = set(subs) | set(cost) | set(revenue)
    return {b: {"billing": subs.get(b), "ai_cost_month": round(cost.get(b, {}).get("cost", 0.0), 4),
                "ai_calls_month": sum(cost.get(b, {}).get("calls", {}).values()), "revenue": revenue.get(b, 0.0)} for b in bids}
