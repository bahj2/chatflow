p = '/app/backend/server.py'
s = open(p).read()


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, f"expected 1 got {n}: {old[:90]}"
    s = s.replace(old, new)


rep('''from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, BackgroundTasks, Query''',
    '''from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, BackgroundTasks, Query, UploadFile, File, Form''')
rep('''from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone''',
    '''from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
import media as M''')

# ---- settings / models ----
rep('''    allowed_emails: List[str] = []


class PublicChatIn(BaseModel):''', '''    allowed_emails: List[str] = []
    voice_replies: bool = True
    voice: str = "nova"
    voxcpm_url: str = ""
    voxcpm_key: str = ""
    voxcpm_for: str = "khmer"
    seller_voice_media_id: str = ""
    seller_voice_text: str = ""


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    price: str = Field(default="", max_length=40)
    description: str = Field(default="", max_length=1000)
    image_media_id: str = ""


class PublicChatIn(BaseModel):''')

# ---- AI with catalog ----
rep('''def system_prompt(s: Settings) -> str:
    faqs = "\\n".join(f"Q: {f.q}\\nA: {f.a}" for f in s.faqs) or "(none)"''', '''SHOW_TAG = re.compile(r"\\[\\[show:([^\\]]*)\\]\\]", re.I)


def catalog_text(products: list) -> str:
    if not products:
        return ""
    rows = "\\n".join(f"{p['id'][:8]} | {p['name']} | {p.get('price') or '-'} | {(p.get('description') or '')[:160]}" for p in products)
    return ("\\n\\nPRODUCT CATALOG (ref | name | price | description):\\n" + rows +
            "\\n\\nWhen the customer asks about products, prices or availability, or seeing a product would clearly help, "
            "mention the product name and price in your reply and END your reply with a tag like [[show:ref1,ref2]] "
            "listing up to 3 refs from the catalog that best match (only refs that exist). Otherwise add no tag.")


def split_show(text: str, products: list) -> tuple:
    refs = [r.strip().lower() for m in SHOW_TAG.findall(text) for r in m.split(",") if r.strip()]
    clean = SHOW_TAG.sub("", text).strip()
    picked = [p for r in refs for p in products if p["id"].startswith(r)]
    seen = set()
    return clean, [p for p in picked if not (p["id"] in seen or seen.add(p["id"]))][:3]


async def load_products(bid: str) -> list:
    return await db.products.find({"business_id": bid, "is_deleted": False}, {"_id": 0}).sort("created_at", -1).to_list(300)


def system_prompt(s: Settings, products: Optional[list] = None) -> str:
    faqs = "\\n".join(f"Q: {f.q}\\nA: {f.a}" for f in s.faqs) or "(none)"''')
rep('''        "Never mention you are an AI model name. Plain text only, no markdown."
    )''', '''        "Never mention you are an AI model name. Plain text only, no markdown."
        + catalog_text(products or [])
    )''')
rep('''async def generate_reply(conv_id: str, s: Settings) -> str:
    t = await transcript(conv_id)
    prompt = f"Conversation so far:\\n{t}\\n\\nWrite the assistant's next reply to the customer. Output only the reply text."
    for attempt in range(3):
        try:
            return await llm(s, system_prompt(s), prompt)''', '''async def generate_reply(conv_id: str, s: Settings, products: list) -> str:
    t = await transcript(conv_id)
    prompt = f"Conversation so far:\\n{t}\\n\\nWrite the assistant's next reply to the customer. Output only the reply text."
    for attempt in range(3):
        try:
            return await llm(s, system_prompt(s, products), prompt)''')

# ---- messages with attachments ----
rep('''async def add_message(conv: dict, role: str, text: str) -> dict:
    conv_id = conv["id"]
    msg = {"id": str(uuid.uuid4()), "conversation_id": conv_id, "business_id": conv["business_id"], "role": role, "text": text, "created_at": now_iso()}
    await db.messages.insert_one(dict(msg))
    upd = {"$set": {"last_message": text[:140], "updated_at": msg["created_at"], "last_role": role}}''', '''async def add_message(conv: dict, role: str, text: str, attachments: Optional[list] = None) -> dict:
    conv_id = conv["id"]
    msg = {"id": str(uuid.uuid4()), "conversation_id": conv_id, "business_id": conv["business_id"], "role": role, "text": text,
           "attachments": attachments or [], "created_at": now_iso()}
    await db.messages.insert_one(dict(msg))
    voice = any(a["type"] == "audio" for a in msg["attachments"])
    upd = {"$set": {"last_message": (("[Voice] " if voice else "") + text)[:140], "updated_at": msg["created_at"], "last_role": role}}''')

rep('''async def handle_incoming(bid: str, channel: str, external_id: str, name: str, text: str):
    conv = await get_or_create_conv(bid, channel, external_id, name)
    await add_message(conv, "user", text)
    s = await get_settings(bid)
    if not (s.auto_reply and conv["ai_enabled"]):
        return None
    try:
        reply = await generate_reply(conv["id"], s)
    except Exception as e:
        logger.exception("AI reply failed: %s", e)
        return None
    msg = await add_message(conv, "ai", reply)
    await send_to_channel(conv, reply, s)
    return msg''', '''async def deliver(conv: dict, s: Settings, text: str, voice_mp3: Optional[bytes], products: list):
    ch, to = conv["channel"], conv["external_id"]
    if ch == "web" or not ((ch == "telegram" and s.telegram_token) or (ch == "messenger" and s.fb_page_token)):
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
                for p in products:
                    cap = f"{p['name']}" + (f" — {p['price']}" if p.get("price") else "")
                    img, doc = await M.load_media(db, p["image_media_id"]) if p.get("image_media_id") else (None, None)
                    if img:
                        r = await h.post(f"{base}/sendPhoto", data={"chat_id": to, "caption": cap}, files={"photo": ("product.jpg", img, doc["content_type"])})
                    else:
                        r = await h.post(f"{base}/sendMessage", json={"chat_id": to, "text": cap})
                    logger.info("telegram product %s %s", r.status_code, r.text[:150])
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
        except Exception as e:
            logger.exception("deliver failed: %s", e)


def product_att(p: dict) -> dict:
    return {"type": "product", "product_id": p["id"], "media_id": p.get("image_media_id") or None, "name": p["name"], "price": p.get("price", "")}


async def handle_incoming(bid: str, channel: str, external_id: str, name: str, text: str, audio: Optional[bytes] = None):
    conv = await get_or_create_conv(bid, channel, external_id, name)
    atts = []
    if audio:
        try:
            mp3 = await M.to_mp3(audio)
            vm = await M.save_media(db, bid, mp3, "audio/mpeg", "voice")
            atts.append({"type": "audio", "media_id": vm["id"]})
            text = await M.transcribe(mp3) or text
        except Exception as e:
            logger.exception("voice in failed: %s", e)
        text = text or "(voice message)"
    await add_message(conv, "user", text, atts)
    s = await get_settings(bid)
    if not (s.auto_reply and conv["ai_enabled"]):
        return None
    products = await load_products(bid)
    try:
        reply, shown = split_show(await generate_reply(conv["id"], s, products), products)
    except Exception as e:
        logger.exception("AI reply failed: %s", e)
        return None
    ratts, voice_mp3 = [], None
    if audio and s.voice_replies:
        try:
            voice_mp3, engine = await M.speak(db, s, reply)
            vm = await M.save_media(db, bid, voice_mp3, "audio/mpeg", "voice")
            ratts.append({"type": "audio", "media_id": vm["id"], "engine": engine})
        except Exception as e:
            logger.exception("voice reply failed: %s", e)
            voice_mp3 = None
    ratts += [product_att(p) for p in shown]
    msg = await add_message(conv, "ai", reply, ratts)
    await deliver(conv, s, reply, voice_mp3, shown)
    return msg''')

# ---- public voice ----
rep('''@api.get("/public/{bid}/chat/{session_id}")''', '''@api.post("/public/{bid}/voice")
async def public_voice(bid: str, request: Request, session_id: str = Form(..., max_length=100), name: str = Form("Website visitor"),
                       file: UploadFile = File(...)):
    bid = await resolve_bid(bid)
    ip = client_ip(request)
    if not rate_ok([(f"s:{bid}:{session_id}", 6, 60), (f"ip:{ip}", 20, 60), (f"iph:{ip}", 150, 3600)]):
        raise HTTPException(429, "You're sending messages too fast. Please wait a moment and try again.")
    data = await file.read()
    if not data or len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "Voice message must be under 10 MB")
    return {"reply": await handle_incoming(bid, "web", session_id, name[:80], "", audio=data)}


@api.get("/public/{bid}/chat/{session_id}")''')

# ---- telegram voice ----
rep('''    data = await request.json()
    m = data.get("message") or {}
    if m.get("text"):
        frm = m.get("from", {})
        name = " ".join(filter(None, [frm.get("first_name"), frm.get("last_name")])) or frm.get("username") or "Telegram user"
        bg.add_task(handle_incoming, bid, "telegram", str(m["chat"]["id"]), name, m["text"])
    return {"ok": True}''', '''    data = await request.json()
    m = data.get("message") or {}
    frm = m.get("from", {})
    name = " ".join(filter(None, [frm.get("first_name"), frm.get("last_name")])) or frm.get("username") or "Telegram user"
    voice = m.get("voice") or m.get("audio")
    if m.get("text"):
        bg.add_task(handle_incoming, bid, "telegram", str(m["chat"]["id"]), name, m["text"])
    elif voice:
        bg.add_task(telegram_voice, bid, s.telegram_token, str(m["chat"]["id"]), name, voice["file_id"], m.get("caption") or "")
    return {"ok": True}


async def telegram_voice(bid, token, chat_id, name, file_id, caption):
    try:
        async with httpx.AsyncClient(timeout=60) as h:
            fp = (await h.get(f"https://api.telegram.org/bot{token}/getFile", params={"file_id": file_id})).json()["result"]["file_path"]
            audio = (await h.get(f"https://api.telegram.org/file/bot{token}/{fp}")).content
    except Exception as e:
        logger.exception("telegram voice download failed: %s", e)
        return
    await handle_incoming(bid, "telegram", chat_id, name, caption, audio=audio)''')

# ---- messenger voice ----
rep('''            text = (ev.get("message") or {}).get("text")
            if text and not ev["message"].get("is_echo"):
                psid = ev["sender"]["id"]
                bg.add_task(handle_incoming, bid, "messenger", psid, f"Messenger user {psid[-4:]}", text)
    return {"ok": True}''', '''            msg = ev.get("message") or {}
            if not msg or msg.get("is_echo"):
                continue
            psid = ev["sender"]["id"]
            audio = next((a for a in msg.get("attachments", []) if a.get("type") == "audio"), None)
            if msg.get("text"):
                bg.add_task(handle_incoming, bid, "messenger", psid, f"Messenger user {psid[-4:]}", msg["text"])
            elif audio and audio.get("payload", {}).get("url"):
                bg.add_task(messenger_voice, bid, psid, audio["payload"]["url"])
    return {"ok": True}


async def messenger_voice(bid, psid, url):
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as h:
            audio = (await h.get(url)).content
    except Exception as e:
        logger.exception("messenger voice download failed: %s", e)
        return
    await handle_incoming(bid, "messenger", psid, f"Messenger user {psid[-4:]}", "", audio=audio)''')

# ---- suggest / ai test with catalog ----
rep('''    s = await get_settings(user["business_id"])
    t = await transcript(cid)
    raw = await llm(s, system_prompt(s), f"Conversation so far''', '''    s = await get_settings(user["business_id"])
    t = await transcript(cid)
    raw = await llm(s, system_prompt(s, await load_products(user["business_id"])), f"Conversation so far''')
rep('''    items = [str(i) for i in items if str(i).strip()][:3] or [raw]''', '''    items = [SHOW_TAG.sub("", str(i)).strip() for i in items if str(i).strip()][:3] or [SHOW_TAG.sub("", raw).strip()]''')
rep('''async def ai_test(body: TestAIIn, user=Depends(current_user)):
    s = await get_settings(user["business_id"])
    return {"reply": await llm(s, system_prompt(s), f"Customer: {body.text}\\n\\nWrite the assistant's reply. Output only the reply text.")}''', '''async def ai_test(body: TestAIIn, user=Depends(current_user)):
    s = await get_settings(user["business_id"])
    products = await load_products(user["business_id"])
    raw = await llm(s, system_prompt(s, products), f"Customer: {body.text}\\n\\nWrite the assistant's reply. Output only the reply text.")
    reply, shown = split_show(raw, products)
    return {"reply": reply, "products": [product_att(p) for p in shown]}


# ---------- Media, products, voice ----------
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@api.get("/media/{mid}")
async def get_media(mid: str):
    data, doc = await M.load_media(db, mid)
    if not data:
        raise HTTPException(404, "Not found")
    return Response(data, media_type=doc["content_type"], headers={"Cache-Control": "public, max-age=86400"})


@api.post("/media/image")
async def upload_image(file: UploadFile = File(...), user=Depends(current_user)):
    if file.content_type not in IMAGE_TYPES:
        raise HTTPException(400, "Please upload a JPG, PNG or WEBP image")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "Image must be under 5 MB")
    doc = await M.save_media(db, user["business_id"], data, file.content_type, "product")
    return {"id": doc["id"]}


@api.get("/products")
async def list_products(user=Depends(current_user)):
    return await load_products(user["business_id"])


@api.post("/products")
async def create_product(body: ProductIn, user=Depends(current_user)):
    bid = user["business_id"]
    if await db.products.count_documents({"business_id": bid, "is_deleted": False}) >= 300:
        raise HTTPException(400, "Product limit reached (300)")
    doc = {"id": str(uuid.uuid4()), "business_id": bid, **body.model_dump(), "is_deleted": False, "created_at": now_iso()}
    await db.products.insert_one(dict(doc))
    return doc


@api.put("/products/{pid}")
async def update_product(pid: str, body: ProductIn, user=Depends(current_user)):
    flt = {"id": pid, "business_id": user["business_id"], "is_deleted": False}
    if not (await db.products.update_one(flt, {"$set": body.model_dump()})).matched_count:
        raise HTTPException(404, "Product not found")
    return await db.products.find_one(flt, {"_id": 0})


@api.delete("/products/{pid}")
async def delete_product(pid: str, user=Depends(current_user)):
    await db.products.update_one({"id": pid, "business_id": user["business_id"]}, {"$set": {"is_deleted": True}})
    return {"ok": True}


@api.post("/settings/seller-voice")
async def seller_voice(file: UploadFile = File(...), text: str = Form(""), user=Depends(current_user)):
    data = await file.read()
    if not data or len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "Voice sample must be under 10 MB")
    try:
        wav = await M.to_wav16k(data)
    except Exception:
        raise HTTPException(400, "Could not read this audio file")
    doc = await M.save_media(db, user["business_id"], wav, "audio/wav", "seller_voice")
    text = text.strip() or await M.transcribe(await M.to_mp3(data))
    await db.settings.update_one({"business_id": user["business_id"]}, {"$set": {"seller_voice_media_id": doc["id"], "seller_voice_text": text}})
    return {"media_id": doc["id"], "text": text}


@api.post("/voice/test")
async def voice_test(body: TestAIIn, user=Depends(current_user)):
    s = await get_settings(user["business_id"])
    try:
        audio, engine = await M.speak(db, s, body.text[:500])
    except Exception as e:
        raise HTTPException(502, f"Voice generation failed: {e}")
    doc = await M.save_media(db, user["business_id"], audio, "audio/mpeg", "voice_test")
    return {"media_id": doc["id"], "engine": engine}''')

# ---- startup ----
rep('''    await db.users.create_index("id", unique=True)
    email, pw''', '''    await db.users.create_index("id", unique=True)
    await db.products.create_index([("business_id", 1), ("is_deleted", 1), ("created_at", -1)])
    await db.media.create_index("id", unique=True)
    try:
        M.init_storage()
    except Exception as e:
        logger.error("Storage init failed: %s", e)
    email, pw''')

open(p, 'w').write(s)
print("ok")
