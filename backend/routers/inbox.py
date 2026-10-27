import re
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

import billing as B
import notion_kb as N
import payments as P
from core import db, now_iso, get_settings, current_user
from ai import system_prompt, llm, transcript, load_products, split_show, order_items, product_att, SHOW_TAG
from conversations import add_message, send_to_channel, load_conv

router = APIRouter(prefix="/api")


class ReplyIn(BaseModel):
    text: str

class ConvPatch(BaseModel):
    ai_enabled: Optional[bool] = None
    unread: Optional[int] = None

class TestAIIn(BaseModel):
    text: str

@router.get("/conversations")
async def list_convs(channel: Optional[str] = None, q: Optional[str] = None, before: Optional[str] = None, before_id: Optional[str] = None,
                     limit: int = Query(50, ge=1, le=100), user=Depends(current_user)):
    bid = user["business_id"]
    flt = {"business_id": bid}
    if channel and channel != "all":
        flt["channel"] = channel
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        hits = await db.messages.distinct("conversation_id", {"business_id": bid, "text": rx})
        flt["$or"] = [{"id": {"$in": hits}}, {"name": rx}, {"last_message": rx}]
    total = await db.conversations.count_documents(flt)
    if before:
        page = [{"updated_at": {"$lt": before}}, {"updated_at": before, "id": {"$lt": before_id or ""}}]
        flt = {"$and": [flt, {"$or": page}]}
    items = await db.conversations.find(flt, {"_id": 0}).sort([("updated_at", -1), ("id", -1)]).to_list(limit + 1)
    return {"items": items[:limit], "has_more": len(items) > limit, "total": total}


@router.get("/conversations/{cid}/messages")
async def conv_messages(cid: str, user=Depends(current_user)):
    await load_conv(cid, user["business_id"])
    msgs = await db.messages.find({"conversation_id": cid}, {"_id": 0}).sort("created_at", -1).to_list(300)
    return list(reversed(msgs))


@router.patch("/conversations/{cid}")
async def patch_conv(cid: str, body: ConvPatch, user=Depends(current_user)):
    await load_conv(cid, user["business_id"])
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if upd:
        await db.conversations.update_one({"id": cid}, {"$set": upd})
    return await load_conv(cid, user["business_id"])

@router.post("/conversations/{cid}/reply")
async def manual_reply(cid: str, body: ReplyIn, user=Depends(current_user)):
    conv = await load_conv(cid, user["business_id"])
    if not body.text.strip():
        raise HTTPException(400, "Empty message")
    msg = await add_message(conv, "agent", body.text.strip())
    await db.conversations.update_one({"id": cid}, {"$set": {"unread": 0}})
    await send_to_channel(conv, body.text.strip(), await get_settings(user["business_id"]))
    return msg


@router.post("/conversations/{cid}/suggest")
async def suggest(cid: str, user=Depends(current_user)):
    await load_conv(cid, user["business_id"])
    s = await get_settings(user["business_id"])
    t = await transcript(cid)
    ctx = system_prompt(s, await load_products(user["business_id"]), await N.knowledge(db, user["business_id"]))
    raw = await llm(s, ctx, f"Conversation so far:\n{t}\n\nGive 3 different short ready-to-send replies to the customer's latest message "
                    "(e.g. one direct answer, one asking a clarifying question, one with a next step/offer). "
                    'Respond ONLY with a JSON array of 3 strings.', user["business_id"], "suggest")
    m = re.search(r"\[.*\]", raw, re.S)
    try:
        items = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        items = []
    items = [SHOW_TAG.sub("", str(i)).strip() for i in items if str(i).strip()][:3] or [SHOW_TAG.sub("", raw).strip()]
    return {"suggestions": items}


@router.post("/ai/test")
async def ai_test(body: TestAIIn, user=Depends(current_user)):
    s = B.effective(await get_settings(user["business_id"]), await B.sub_status(db, user["business_id"]))
    products = await load_products(user["business_id"])
    raw = await llm(s, system_prompt(s, products, await N.knowledge(db, user["business_id"])), f"Customer: {body.text}\n\nWrite the assistant's reply. Output only the reply text.",
                    user["business_id"], "test")
    reply, shown = split_show(raw, products)
    items = order_items(raw, products) if P.enabled(s) else []
    order = None
    if items:
        prices = [P.parse_price(p.get("price", "")) for p, _ in items]
        if all(prices) and len({c for _, c in prices}) == 1:
            order = P.fmt_amount(sum(a * q for (a, _), (_, q) in zip(prices, items)), prices[0][1])
    return {"reply": reply, "products": [product_att(p) for p in shown], "order_total": order}

@router.get("/stats")
async def stats(user=Depends(current_user)):
    bid = user["business_id"]
    res = {"total": await db.conversations.count_documents({"business_id": bid})}
    for ch in ["telegram", "messenger"]:
        res[ch] = await db.conversations.count_documents({"business_id": bid, "channel": ch})
    res["ai_replies"] = await db.messages.count_documents({"business_id": bid, "role": "ai"})
    res["agent_replies"] = await db.messages.count_documents({"business_id": bid, "role": "agent"})
    return res

SUMMARY_PROMPT = (
    "Analyse this customer conversation for the business owner. Respond ONLY with a JSON object with keys: "
    '"intent" (what the customer wants, max 5 words), "summary" (1-2 short sentences), '
    '"stage" (one of: "New lead", "Hot lead", "Question", "Support", "Complaint", "Resolved"), '
    '"details" (array of up to 4 short key facts like product, budget, location, date, contact - only if mentioned), '
    '"next_step" (one short recommended action for the business). Write in the same language as the customer.'
)


@router.post("/conversations/{cid}/summary")
async def conv_summary(cid: str, force: bool = False, user=Depends(current_user)):
    conv = await load_conv(cid, user["business_id"])
    count = await db.messages.count_documents({"conversation_id": cid})
    if not force and conv.get("summary") and conv.get("summary_count") == count:
        return conv["summary"]
    if not await db.messages.count_documents({"conversation_id": cid, "role": "user"}):
        return None
    s = await get_settings(user["business_id"])
    t = await transcript(cid, 40)
    lang = "the same language the customer writes in (English if the customer writes in English)" if s.language == "auto" else s.language
    raw = await llm(s, f"You are a sales & support analyst for '{s.business_name}'. Business info: {s.business_info or '(not provided)'}",
                    f"{SUMMARY_PROMPT} All values must be written in {lang}.\n\nConversation:\n{t}", user["business_id"], "summary")
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        data = {}
    summary = {"intent": str(data.get("intent", ""))[:60], "summary": str(data.get("summary", raw))[:400],
               "stage": str(data.get("stage", "Question")), "details": [str(d) for d in data.get("details", [])][:4],
               "next_step": str(data.get("next_step", "")), "updated_at": now_iso()}
    await db.conversations.update_one({"id": cid}, {"$set": {"summary": summary, "summary_count": count}})
    return summary
