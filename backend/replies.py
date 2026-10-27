"""Incoming customer messages: transcribe voice, AI reply, voice / product photos / KHQR delivery."""
import json
from typing import Optional

import httpx

import billing as B
import media as M
import notion_kb as N
import payments as P
from core import db, logger, Settings, get_settings
from ai import generate_reply, split_show, order_items, load_products, product_att
from conversations import get_or_create_conv, add_message, send_to_channel
from orders import QR_FAIL, khqr_caption, khqr_att, order_problem, create_order


async def deliver(conv: dict, s: Settings, text: str, voice_mp3: Optional[bytes], products: list, order: Optional[dict] = None):
    ch, to = conv["channel"], conv["external_id"]
    if not ((ch == "telegram" and s.telegram_token) or (ch == "messenger" and s.fb_page_token)):
        return
    if voice_mp3 is None:
        await send_to_channel(conv, text, s)
    async with httpx.AsyncClient(timeout=60) as h:
        try:
            if ch == "telegram":
                base = f"https://api.telegram.org/bot{s.telegram_token}"
                if voice_mp3 is not None:
                    r = await h.post(f"{base}/sendVoice", data={"chat_id": to}, files={"voice": ("reply.mp3", voice_mp3, "audio/mpeg")})
                    logger.info("telegram voice %s %s", r.status_code, r.text[:150])
                photos, texts = [], []
                for p in products:
                    cap = f"{p['name']}" + (f" — {p['price']}" if p.get("price") else "")
                    img, doc = await M.load_media(db, p["image_media_id"]) if p.get("image_media_id") else (None, None)
                    if img:
                        photos.append((cap, img, doc["content_type"]))
                    else:
                        texts.append(cap)
                if len(photos) == 1:
                    cap, img, ct = photos[0]
                    r = await h.post(f"{base}/sendPhoto", data={"chat_id": to, "caption": cap}, files={"photo": ("product.jpg", img, ct)})
                    logger.info("telegram product %s %s", r.status_code, r.text[:150])
                    if r.status_code != 200:
                        texts = [cap] + texts
                elif photos:  # album of up to 10 photos, each with its own caption
                    media = [{"type": "photo", "media": f"attach://p{i}", "caption": cap} for i, (cap, _, _) in enumerate(photos)]
                    files = {f"p{i}": (f"product{i}.jpg", img, ct) for i, (_, img, ct) in enumerate(photos)}
                    r = await h.post(f"{base}/sendMediaGroup", data={"chat_id": to, "media": json.dumps(media)}, files=files)
                    logger.info("telegram products album %s %s", r.status_code, r.text[:150])
                    if r.status_code != 200:
                        texts = [cap for cap, _, _ in photos] + texts
                if texts:
                    r = await h.post(f"{base}/sendMessage", json={"chat_id": to, "text": "\n".join(texts)})
                    logger.info("telegram product text %s %s", r.status_code, r.text[:150])
                if order:
                    png, _ = await M.load_media(db, order["qr_media_id"])
                    data = {"chat_id": to, "caption": khqr_caption(order)}
                    if order.get("deeplink"):
                        data["reply_markup"] = json.dumps({"inline_keyboard": [[{"text": "Pay with Bakong", "url": order["deeplink"]}]]})
                    r = await h.post(f"{base}/sendPhoto", data=data, files={"photo": ("khqr.png", png, "image/png")})
                    logger.info("telegram khqr %s %s", r.status_code, r.text[:150])
            else:
                url, params = "https://graph.facebook.com/v21.0/me/messages", {"access_token": s.fb_page_token}
                rcpt = json.dumps({"id": to})

                async def attach(kind, data, fname, ct):
                    msg = json.dumps({"attachment": {"type": kind, "payload": {"is_reusable": False}}})
                    r = await h.post(url, params=params, data={"recipient": rcpt, "message": msg, "messaging_type": "RESPONSE"}, files={"filedata": (fname, data, ct)})
                    logger.info("messenger %s %s %s", kind, r.status_code, r.text[:150])
                if voice_mp3 is not None:
                    await attach("audio", voice_mp3, "reply.mp3", "audio/mpeg")
                for p in products:
                    img, doc = await M.load_media(db, p["image_media_id"]) if p.get("image_media_id") else (None, None)
                    if img:
                        await attach("image", img, "product.jpg", doc["content_type"])
                    await send_to_channel(conv, f"{p['name']}" + (f" — {p['price']}" if p.get("price") else ""), s)
                if order:
                    png, _ = await M.load_media(db, order["qr_media_id"])
                    await attach("image", png, "khqr.png", "image/png")
                    await send_to_channel(conv, khqr_caption(order) + (f"\n{order['deeplink']}" if order.get("deeplink") else ""), s)
        except Exception as e:
            logger.exception("deliver failed: %s", e)

async def handle_incoming(bid: str, channel: str, external_id: str, name: str, text: str, audio: Optional[bytes] = None):
    conv = await get_or_create_conv(bid, channel, external_id, name)
    atts = []
    if audio:
        try:
            mp3 = await M.to_mp3(audio)
            vm = await M.save_media(db, bid, mp3, "audio/mpeg", "voice")
            atts.append({"type": "audio", "media_id": vm["id"]})
            text = (await M.transcribe(mp3) or "").strip() or text
            await B.record_stt(db, bid, len(mp3) * 8 / 64000)  # to_mp3 encodes at 64 kbit/s
        except Exception as e:
            logger.exception("voice in failed: %s", e)
        text = text or "(voice message)"
    await add_message(conv, "user", text, atts)
    s = await get_settings(bid)
    if not (s.auto_reply and conv["ai_enabled"]):
        return None
    plan = await B.sub_status(db, bid)
    s = B.effective(s, plan)
    greeting = s.greeting.strip()
    if greeting and (conv.get("is_new") or (channel == "telegram" and text.strip().lower().startswith("/start"))):
        gmsg = await add_message(conv, "ai", greeting)
        await send_to_channel(conv, greeting, s)
        if text.strip().lower().startswith("/start"):
            return gmsg
    slot = await B.reserve(db, bid)
    if not slot:
        logger.info("AI replies paused for %s (%s)", bid, plan["reason"] or "used_up")
        return None
    products = await load_products(bid)
    knowledge = await N.knowledge(db, bid) if plan["pro"] else ""
    try:
        raw = await generate_reply(conv["id"], s, products, spoken=bool(audio and s.voice_replies), knowledge=knowledge, bid=bid)
    except Exception as e:
        logger.exception("AI reply failed: %s", e)
        await B.refund(db, bid, slot)
        return None
    reply, shown = split_show(raw, products)
    items = order_items(raw, products) if P.enabled(s) else []
    problem = order_problem(items) if items else ""
    if problem:
        items = []
        note = (f"No payment QR can be sent because {problem}. Rewrite your reply for this: do not say that a QR or payment code "
                "is being sent, and add no [[order]] tag.")
        try:
            raw = await generate_reply(conv["id"], s, products, spoken=bool(audio and s.voice_replies), knowledge=knowledge, note=note, bid=bid)
            reply, shown = split_show(raw, products)
        except Exception as e:
            logger.warning("order-problem rewrite failed: %s", e)
    order = await create_order(conv, s, items) if items else None
    if items and not order:
        reply += "\n\n" + (QR_FAIL["km"] if M.KHMER.search(reply) else QR_FAIL["en"])
    ratts, voice_mp3 = [], None
    if audio and s.voice_replies:
        try:
            voice_mp3, engine = await M.speak(db, s, reply)
            vm = await M.save_media(db, bid, voice_mp3, "audio/mpeg", "voice")
            ratts.append({"type": "audio", "media_id": vm["id"], "engine": engine})
        except Exception as e:
            logger.exception("voice reply failed: %s", e)
            voice_mp3 = None
    ratts += [product_att(p) for p in shown] + ([khqr_att(order)] if order else [])
    msg = await add_message(conv, "ai", reply, ratts)
    await deliver(conv, s, reply, voice_mp3, shown, order)
    return msg
