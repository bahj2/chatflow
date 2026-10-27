"""Customer orders paid by Bakong KHQR, and the background payment checker."""
import asyncio
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import billing as B
import media as M
import payments as P
from core import db, logger, now_iso, Settings, get_settings, platform_settings
from conversations import add_message, send_to_channel


QR_FAIL = {"en": "(Sorry, the payment QR could not be created right now. Our team will send you the payment details.)",
           "km": "(សូមអភ័យទោស មិនអាចបង្កើត QR ទូទាត់បានទេពេលនេះ។ ក្រុមការងាររបស់យើងនឹងផ្ញើព័ត៌មានទូទាត់ជូន។)"}
PAID_MSG = {"en": "Payment received ✅ Thank you! Order {number} · {amount} is confirmed.",
            "km": "បានទទួលការទូទាត់ ✅ សូមអរគុណ! ការកម្ម៉ង់ {number} · {amount} ត្រូវបានបញ្ជាក់។"}


def khqr_caption(o: dict) -> str:
    return f"Bakong KHQR · {P.fmt_amount(o['total'], o['currency'])} · Order {o['number']}\nScan with any bank app (ABA, ACLEDA, Wing, Bakong…) · valid {P.QR_MINUTES} min"


def khqr_att(o: dict) -> dict:
    return {"type": "khqr", "order_id": o["id"], "media_id": o["qr_media_id"], "number": o["number"], "total": o["total"],
            "currency": o["currency"], "amount_text": P.fmt_amount(o["total"], o["currency"]), "expires_at": o["expires_at"],
            "status": o["status"], "deeplink": o.get("deeplink")}


async def set_att_status(order_ids: list, status: str):
    if order_ids:
        await db.messages.update_many({"attachments.order_id": {"$in": order_ids}}, {"$set": {"attachments.$[a].status": status}},
                                      array_filters=[{"a.order_id": {"$in": order_ids}}])


def order_problem(items: list) -> str:
    prices = [P.parse_price(p.get("price", "")) for p, _ in items]
    if not all(prices):
        return "some of these products have no single exact price (e.g. a price range), so a team member must confirm the price first"
    if len({c for _, c in prices}) > 1:
        return "the products are priced in different currencies (USD and KHR); ask the customer to order the USD and the KHR products separately"
    return ""


async def create_order(conv: dict, s: Settings, items: list) -> Optional[dict]:
    lines, currency = [], None
    for p, qty in items:
        price = P.parse_price(p.get("price", ""))
        if not price or (currency and price[1] != currency):
            logger.warning("order skipped: price %r not usable (currency %s)", p.get("price"), currency)
            return None
        currency = price[1]
        lines.append({"product_id": p["id"], "name": p["name"], "price": p.get("price", ""), "unit": price[0], "qty": qty,
                      "total": round(price[0] * qty, 2)})
    total = round(sum(x["total"] for x in lines), 2 if currency == "USD" else 0)
    number = "RF-" + secrets.token_hex(4).upper()
    try:
        q = await P.make_qr(s, total, currency, number)
    except Exception as e:
        logger.warning("KHQR creation failed: %s", e)
        return None
    media = await M.save_media(db, conv["business_id"], q["png"], "image/png", "khqr")
    stale = [o["id"] async for o in db.orders.find({"business_id": conv["business_id"], "conversation_id": conv["id"], "status": "pending"}, {"_id": 0, "id": 1})]
    if stale:
        await db.orders.update_many({"id": {"$in": stale}}, {"$set": {"status": "cancelled", "updated_at": now_iso()}})
        await set_att_status(stale, "cancelled")
    now = datetime.now(timezone.utc)
    order = {"id": str(uuid.uuid4()), "business_id": conv["business_id"], "conversation_id": conv["id"], "channel": conv["channel"],
             "customer": conv.get("name", ""), "number": number, "items": lines, "total": total, "currency": currency, "mode": q["mode"],
             "qr": q["qr"], "md5": q["md5"], "deeplink": q["deeplink"], "qr_media_id": media["id"], "status": "pending",
             "created_at": now.isoformat(), "expires_at": (now + timedelta(minutes=P.QR_MINUTES)).isoformat(), "paid_at": None, "paid_by": ""}
    await db.orders.insert_one(dict(order))
    return order


async def settle_order(order: dict, by: str) -> bool:
    if not await db.orders.find_one_and_update({"id": order["id"], "status": {"$ne": "paid"}},
                                               {"$set": {"status": "paid", "paid_at": now_iso(), "paid_by": by, "updated_at": now_iso()}}):
        return False
    await set_att_status([order["id"]], "paid")
    conv = await db.conversations.find_one({"id": order["conversation_id"]}, {"_id": 0})
    if not conv:
        return True
    last = await db.messages.find_one({"conversation_id": conv["id"], "role": "user"}, {"_id": 0, "text": 1}, sort=[("created_at", -1)])
    lang = "km" if last and M.KHMER.search(last.get("text", "")) else "en"
    text = PAID_MSG[lang].format(number=order["number"], amount=P.fmt_amount(order["total"], order["currency"]))
    await add_message(conv, "ai", text)
    try:
        await send_to_channel(conv, text, await get_settings(order["business_id"]))
    except Exception as e:
        logger.warning("paid notice not delivered: %s", e)
    return True


async def expire_orders():
    ids = [o["id"] async for o in db.orders.find({"status": "pending", "expires_at": {"$lt": now_iso()}}, {"_id": 0, "id": 1})]
    if ids:
        await db.orders.update_many({"id": {"$in": ids}, "status": "pending"}, {"$set": {"status": "expired", "updated_at": now_iso()}})
        await set_att_status(ids, "expired")


async def poll_relay(late: bool):
    # Relay QRs stay payable for 1 day, so expired/replaced ones are re-checked once a minute for late payments.
    flt = {"mode": "relay", "status": "pending"}
    if late:
        flt = {"mode": "relay", "status": {"$in": ["pending", "expired", "cancelled"]},
               "created_at": {"$gt": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}}
    groups = {}
    async for o in db.orders.find(flt, {"_id": 0, "qr": 0}):
        groups.setdefault(o["business_id"], []).append(o)
    sem = asyncio.Semaphore(5)

    async def check(bid, orders):
        async with sem:
            token = (await get_settings(bid)).khqr_token
            if not token.startswith(P.RELAY_PREFIX):
                return
            for i in range(0, len(orders), 50):
                chunk = orders[i:i + 50]
                try:
                    paid = set(await P.bulk_paid(token, [o["md5"] for o in chunk]))
                except P.PaymentError as e:
                    logger.warning("KHQR.dev check failed for %s: %s", bid, e)
                    return
                for o in chunk:
                    if o["md5"] in paid:
                        await settle_order(o, "auto")
    await asyncio.gather(*(check(b, os_) for b, os_ in groups.items()))


async def payments_loop():
    tick = 0
    while True:
        try:
            await expire_orders()
            await poll_relay(late=tick % 12 == 0)
            if tick % 6 == 0:
                await B.poll(db, await platform_settings())
        except Exception as e:
            logger.exception("payments loop: %s", e)
        tick += 1
        await asyncio.sleep(5)
