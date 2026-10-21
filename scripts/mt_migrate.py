import re
p = '/app/backend/server.py'
s = open(p).read()


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, f"expected {count} got {n}: {old[:80]}"
    s = s.replace(old, new)


# ---- auth ----
rep('''    await db.login_attempts.delete_one({"identifier": ident})
    return issue_token(user)


def issue_token(user: dict) -> dict:
    token = jwt.encode({"sub": user["id"], "email": user["email"], "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "access"}, JWT_SECRET, algorithm=JWT_ALG)
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user.get("name"), "picture": user.get("picture"), "role": user.get("role")}}
''', '''    await db.login_attempts.delete_one({"identifier": ident})
    return await issue_token(user)


async def issue_token(user: dict) -> dict:
    token = jwt.encode({"sub": user["id"], "email": user["email"], "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "access"}, JWT_SECRET, algorithm=JWT_ALG)
    biz = await db.businesses.find_one({"id": user["business_id"]}, {"_id": 0, "name": 1})
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user.get("name"), "picture": user.get("picture"),
                                     "role": user.get("role"), "business_id": user["business_id"], "business_name": (biz or {}).get("name")}}


EMAIL_RE = r"[^@\\s]+@[^@\\s]+\\.[^@\\s]+"


async def create_business(name: str, owner_id: str) -> str:
    bid = str(uuid.uuid4())
    await db.businesses.insert_one({"id": bid, "name": name, "owner_id": owner_id, "created_at": now_iso()})
    await db.settings.insert_one({"business_id": bid, **Settings(business_name=name).model_dump()})
    return bid


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=128)
    business_name: str = Field(min_length=1, max_length=80)


@api.post("/auth/register")
async def register(body: RegisterIn, request: Request):
    email = body.email.strip().lower()
    if not re.fullmatch(EMAIL_RE, email):
        raise HTTPException(400, "Please enter a valid email")
    if not rate_ok([(f"reg:{client_ip(request)}", 5, 3600)]):
        raise HTTPException(429, "Too many sign-ups from this network. Try again later.")
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "An account with this email already exists. Please sign in.")
    uid = str(uuid.uuid4())
    bid = await create_business(body.business_name.strip(), uid)
    user = {"id": uid, "email": email, "name": body.business_name.strip(), "password_hash": hash_pw(body.password),
            "role": "owner", "business_id": bid, "created_at": now_iso()}
    await db.users.insert_one(dict(user))
    return await issue_token(user)
''')

rep('''    email = g["email"].strip().lower()
    s = await get_settings()
    allowed = {e.strip().lower() for e in s.allowed_emails} | {os.environ['ADMIN_EMAIL'].lower()}
    if email not in allowed:
        raise HTTPException(403, f"{email} is not allowed. Sign in with your password and add it in AI Settings → Team access.")
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if user:
        await db.users.update_one({"email": email}, {"$set": {"picture": g.get("picture"), "name": user.get("name") or g.get("name")}})
        user["picture"] = g.get("picture")
    else:
        user = {"id": str(uuid.uuid4()), "email": email, "name": g.get("name"), "picture": g.get("picture"), "role": "admin", "auth": "google", "created_at": now_iso()}
        await db.users.insert_one(dict(user))
    return issue_token(user)''', '''    email = g["email"].strip().lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if user:
        await db.users.update_one({"email": email}, {"$set": {"picture": g.get("picture"), "name": user.get("name") or g.get("name")}})
        user["picture"] = g.get("picture")
    else:
        uid = str(uuid.uuid4())
        team = await db.settings.find_one({"allowed_emails": email}, {"_id": 0, "business_id": 1})
        if team:
            bid, role = team["business_id"], "member"
        else:
            bid, role = await create_business(f"{g.get('name') or email.split('@')[0]}'s business", uid), "owner"
        user = {"id": uid, "email": email, "name": g.get("name"), "picture": g.get("picture"), "role": role, "auth": "google",
                "business_id": bid, "created_at": now_iso()}
        await db.users.insert_one(dict(user))
    return await issue_token(user)''')

rep('''@api.get("/auth/me")
async def me(user=Depends(current_user)):
    return user''', '''@api.get("/auth/me")
async def me(user=Depends(current_user)):
    biz = await db.businesses.find_one({"id": user["business_id"]}, {"_id": 0, "name": 1})
    return {**user, "business_name": (biz or {}).get("name")}


async def superadmin(user=Depends(current_user)):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Platform admin only")
    return user


@api.get("/admin/businesses")
async def admin_businesses(user=Depends(superadmin)):
    bizs = await db.businesses.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    convs = {d["_id"]: d["n"] async for d in db.conversations.aggregate([{"$group": {"_id": "$business_id", "n": {"$sum": 1}}}])}
    ai = {d["_id"]: d["n"] async for d in db.messages.aggregate([{"$match": {"role": "ai"}}, {"$group": {"_id": "$business_id", "n": {"$sum": 1}}}])}
    owners = {u["id"]: u["email"] async for u in db.users.find({"id": {"$in": [b["owner_id"] for b in bizs]}}, {"_id": 0, "id": 1, "email": 1})}
    tg = {d["business_id"] async for d in db.settings.find({"telegram_token": {"$ne": ""}}, {"_id": 0, "business_id": 1})}
    fb = {d["business_id"] async for d in db.settings.find({"fb_page_token": {"$ne": ""}}, {"_id": 0, "business_id": 1})}
    return [{**b, "owner_email": owners.get(b["owner_id"]), "conversations": convs.get(b["id"], 0), "ai_replies": ai.get(b["id"], 0),
             "telegram": b["id"] in tg, "messenger": b["id"] in fb} for b in bizs]''')

# ---- settings ----
rep('''async def get_settings() -> Settings:
    doc = await db.settings.find_one({"key": "main"}, {"_id": 0, "key": 0})
    return Settings(**(doc or {}))


@api.get("/settings")
async def read_settings(user=Depends(current_user)):
    return (await get_settings()).model_dump()
''', '''async def get_settings(bid: str) -> Settings:
    doc = await db.settings.find_one({"business_id": bid}, {"_id": 0, "business_id": 0})
    return Settings(**(doc or {}))


@api.get("/settings")
async def read_settings(user=Depends(current_user)):
    return (await get_settings(user["business_id"])).model_dump()
''')
rep('''    await db.settings.update_one({"key": "main"}, {"$set": body.model_dump()}, upsert=True)
    return body.model_dump()''', '''    await db.settings.update_one({"business_id": user["business_id"]}, {"$set": body.model_dump()}, upsert=True)
    await db.businesses.update_one({"id": user["business_id"]}, {"$set": {"name": body.business_name}})
    return body.model_dump()''')
rep('r"[^@\\s]+@[^@\\s]+\\.[^@\\s]+", e.strip())', 'EMAIL_RE, e.strip())')

# ---- AI retry ----
rep('''async def generate_reply(conv_id: str, s: Settings) -> str:
    t = await transcript(conv_id)
    return await llm(s, system_prompt(s), f"Conversation so far:\\n{t}\\n\\nWrite the assistant's next reply to the customer. Output only the reply text.")''',
'''async def generate_reply(conv_id: str, s: Settings) -> str:
    t = await transcript(conv_id)
    prompt = f"Conversation so far:\\n{t}\\n\\nWrite the assistant's next reply to the customer. Output only the reply text."
    for attempt in range(3):
        try:
            return await llm(s, system_prompt(s), prompt)
        except Exception as e:
            if attempt == 2:
                raise
            logger.warning("AI reply retry %s: %s", attempt + 1, e)
            await asyncio.sleep(1.5 * (attempt + 1))''')

# ---- conversations core ----
rep('''async def get_or_create_conv(channel: str, external_id: str, name: str) -> dict:
    conv = await db.conversations.find_one({"channel": channel, "external_id": external_id}, {"_id": 0})
    if conv:
        return conv
    conv = {"id": str(uuid.uuid4()), "channel": channel, "external_id": external_id, "name": name or "Guest",''',
'''async def get_or_create_conv(bid: str, channel: str, external_id: str, name: str) -> dict:
    key = {"business_id": bid, "channel": channel, "external_id": external_id}
    conv = await db.conversations.find_one(key, {"_id": 0})
    if conv:
        return conv
    conv = {"id": str(uuid.uuid4()), **key, "name": name or "Guest",''')
rep('''        return await db.conversations.find_one({"channel": channel, "external_id": external_id}, {"_id": 0})''',
    '''        return await db.conversations.find_one(key, {"_id": 0})''')
rep('''async def add_message(conv_id: str, role: str, text: str) -> dict:
    msg = {"id": str(uuid.uuid4()), "conversation_id": conv_id, "role": role, "text": text, "created_at": now_iso()}
    await db.messages.insert_one(dict(msg))''', '''async def add_message(conv: dict, role: str, text: str) -> dict:
    conv_id = conv["id"]
    msg = {"id": str(uuid.uuid4()), "conversation_id": conv_id, "business_id": conv["business_id"], "role": role, "text": text, "created_at": now_iso()}
    await db.messages.insert_one(dict(msg))''')
rep('''async def handle_incoming(channel: str, external_id: str, name: str, text: str):
    conv = await get_or_create_conv(channel, external_id, name)
    await add_message(conv["id"], "user", text)
    s = await get_settings()''', '''async def handle_incoming(bid: str, channel: str, external_id: str, name: str, text: str):
    conv = await get_or_create_conv(bid, channel, external_id, name)
    await add_message(conv, "user", text)
    s = await get_settings(bid)''')
rep('''    msg = await add_message(conv["id"], "ai", reply)''', '''    msg = await add_message(conv, "ai", reply)''')

# ---- public ----
rep('''@api.get("/public/info")
async def public_info():
    s = await get_settings()
    return {"business_name": s.business_name, "greeting": s.greeting}
''', '''DEFAULT_BID = {}


async def resolve_bid(bid: str) -> str:
    if bid == "default":
        if "v" not in DEFAULT_BID:
            admin = await db.users.find_one({"email": os.environ['ADMIN_EMAIL'].lower()}, {"_id": 0, "business_id": 1})
            DEFAULT_BID["v"] = admin["business_id"]
        return DEFAULT_BID["v"]
    if not await db.businesses.find_one({"id": bid}, {"_id": 1}):
        raise HTTPException(404, "Business not found")
    return bid


@api.get("/public/{bid}/info")
async def public_info(bid: str):
    s = await get_settings(await resolve_bid(bid))
    return {"business_name": s.business_name, "greeting": s.greeting}
''')
rep('''@api.post("/public/chat")
async def public_chat(body: PublicChatIn, request: Request):''', '''@api.post("/public/{bid}/chat")
async def public_chat(bid: str, body: PublicChatIn, request: Request):
    bid = await resolve_bid(bid)''')
rep('''    if not rate_ok([(f"s:{body.session_id}", 6, 60),''', '''    if not rate_ok([(f"s:{bid}:{body.session_id}", 6, 60),''')
rep('''    msg = await handle_incoming("web", body.session_id,''', '''    msg = await handle_incoming(bid, "web", body.session_id,''')
rep('''@api.get("/public/chat/{session_id}")
async def public_history(session_id: str):
    conv = await db.conversations.find_one({"channel": "web", "external_id": session_id}, {"_id": 0})''', '''@api.get("/public/{bid}/chat/{session_id}")
async def public_history(bid: str, session_id: str):
    bid = await resolve_bid(bid)
    conv = await db.conversations.find_one({"business_id": bid, "channel": "web", "external_id": session_id}, {"_id": 0})''')

# ---- webhooks ----
rep('''def tg_secret(token: str) -> str:
    return hashlib.sha256(f"{JWT_SECRET}:{token}".encode()).hexdigest()


@api.post("/webhooks/telegram/{secret}")
async def telegram_webhook(secret: str, request: Request, bg: BackgroundTasks):
    s = await get_settings()
    if not s.telegram_token or secret != s.telegram_token.split(":")[0] or request.headers.get("X-Telegram-Bot-Api-Secret-Token") != tg_secret(s.telegram_token):''',
'''def tg_secret(bid: str, token: str) -> str:
    return hashlib.sha256(f"{JWT_SECRET}:{bid}:{token}".encode()).hexdigest()


@api.post("/webhooks/telegram/{bid}")
async def telegram_webhook(bid: str, request: Request, bg: BackgroundTasks):
    s = await get_settings(bid)
    if not s.telegram_token or not hmac.compare_digest(request.headers.get("X-Telegram-Bot-Api-Secret-Token", ""), tg_secret(bid, s.telegram_token)):''')
rep('''        bg.add_task(handle_incoming, "telegram",''', '''        bg.add_task(handle_incoming, bid, "telegram",''')
rep('''@api.get("/webhooks/messenger")
async def messenger_verify(request: Request):
    s = await get_settings()''', '''@api.get("/webhooks/messenger/{bid}")
async def messenger_verify(bid: str, request: Request):
    s = await get_settings(bid)''')
rep('''@api.post("/webhooks/messenger")
async def messenger_webhook(request: Request, bg: BackgroundTasks):
    raw = await request.body()
    s = await get_settings()''', '''@api.post("/webhooks/messenger/{bid}")
async def messenger_webhook(bid: str, request: Request, bg: BackgroundTasks):
    raw = await request.body()
    s = await get_settings(bid)''')
rep('''                bg.add_task(handle_incoming, "messenger",''', '''                bg.add_task(handle_incoming, bid, "messenger",''')

# ---- admin inbox ----
rep('''@api.get("/conversations")
async def list_convs(channel: Optional[str] = None, q: Optional[str] = None, user=Depends(current_user)):
    flt = {}
    if channel and channel != "all":
        flt["channel"] = channel
    if q:
        hits = await db.messages.distinct("conversation_id", {"text": {"$regex": re.escape(q), "$options": "i"}})
        flt["$or"] = [{"id": {"$in": hits}}, {"name": {"$regex": re.escape(q), "$options": "i"}}, {"last_message": {"$regex": re.escape(q), "$options": "i"}}]
    return await db.conversations.find(flt, {"_id": 0}).sort("updated_at", -1).to_list(300)


@api.get("/conversations/{cid}/messages")
async def conv_messages(cid: str, user=Depends(current_user)):
    return await db.messages.find({"conversation_id": cid}, {"_id": 0}).sort("created_at", 1).to_list(1000)


@api.patch("/conversations/{cid}")
async def patch_conv(cid: str, body: ConvPatch, user=Depends(current_user)):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if upd:
        await db.conversations.update_one({"id": cid}, {"$set": upd})
    conv = await db.conversations.find_one({"id": cid}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Not found")
    return conv


async def load_conv(cid):
    conv = await db.conversations.find_one({"id": cid}, {"_id": 0})''', '''@api.get("/conversations")
async def list_convs(channel: Optional[str] = None, q: Optional[str] = None, before: Optional[str] = None,
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
        flt["updated_at"] = {"$lt": before}
    items = await db.conversations.find(flt, {"_id": 0}).sort("updated_at", -1).to_list(limit + 1)
    return {"items": items[:limit], "has_more": len(items) > limit, "total": total}


@api.get("/conversations/{cid}/messages")
async def conv_messages(cid: str, user=Depends(current_user)):
    await load_conv(cid, user["business_id"])
    msgs = await db.messages.find({"conversation_id": cid}, {"_id": 0}).sort("created_at", -1).to_list(300)
    return list(reversed(msgs))


@api.patch("/conversations/{cid}")
async def patch_conv(cid: str, body: ConvPatch, user=Depends(current_user)):
    await load_conv(cid, user["business_id"])
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if upd:
        await db.conversations.update_one({"id": cid}, {"$set": upd})
    return await load_conv(cid, user["business_id"])


async def load_conv(cid, bid):
    conv = await db.conversations.find_one({"id": cid, "business_id": bid}, {"_id": 0})''')
rep('''    conv = await load_conv(cid)
    if not body.text.strip():
        raise HTTPException(400, "Empty message")
    msg = await add_message(cid, "agent", body.text.strip())
    await db.conversations.update_one({"id": cid}, {"$set": {"unread": 0}})
    await send_to_channel(conv, body.text.strip(), await get_settings())''', '''    conv = await load_conv(cid, user["business_id"])
    if not body.text.strip():
        raise HTTPException(400, "Empty message")
    msg = await add_message(conv, "agent", body.text.strip())
    await db.conversations.update_one({"id": cid}, {"$set": {"unread": 0}})
    await send_to_channel(conv, body.text.strip(), await get_settings(user["business_id"]))''')
rep('''    await load_conv(cid)
    s = await get_settings()
    t = await transcript(cid)''', '''    await load_conv(cid, user["business_id"])
    s = await get_settings(user["business_id"])
    t = await transcript(cid)''')
rep('''async def ai_test(body: TestAIIn, user=Depends(current_user)):
    s = await get_settings()''', '''async def ai_test(body: TestAIIn, user=Depends(current_user)):
    s = await get_settings(user["business_id"])''')
rep('''    res = {"total": await db.conversations.count_documents({})}
    for ch in ["web", "telegram", "messenger"]:
        res[ch] = await db.conversations.count_documents({"channel": ch})
    res["ai_replies"] = await db.messages.count_documents({"role": "ai"})
    res["agent_replies"] = await db.messages.count_documents({"role": "agent"})''', '''    bid = user["business_id"]
    res = {"total": await db.conversations.count_documents({"business_id": bid})}
    for ch in ["web", "telegram", "messenger"]:
        res[ch] = await db.conversations.count_documents({"business_id": bid, "channel": ch})
    res["ai_replies"] = await db.messages.count_documents({"business_id": bid, "role": "ai"})
    res["agent_replies"] = await db.messages.count_documents({"business_id": bid, "role": "agent"})''')

# ---- channels ----
rep('''async def telegram_connect(body: TelegramConnectIn, user=Depends(current_user)):
    s = await get_settings()
    if not s.telegram_token:
        raise HTTPException(400, "Save your Telegram bot token first")
    url = f"{body.base_url.rstrip('/')}/api/webhooks/telegram/{s.telegram_token.split(':')[0]}"''', '''async def telegram_connect(body: TelegramConnectIn, user=Depends(current_user)):
    bid = user["business_id"]
    s = await get_settings(bid)
    if not s.telegram_token:
        raise HTTPException(400, "Save your Telegram bot token first")
    url = f"{body.base_url.rstrip('/')}/api/webhooks/telegram/{bid}"''')
rep('''            await db.settings.update_one({"key": "main"}, {"$set": {"telegram_token": ""}})''', '''            await db.settings.update_one({"business_id": bid}, {"$set": {"telegram_token": ""}})''')
rep('''json={"url": url, "secret_token": tg_secret(s.telegram_token)}''', '''json={"url": url, "secret_token": tg_secret(bid, s.telegram_token)}''')
rep('''async def channels_status(user=Depends(current_user)):
    s = await get_settings()''', '''async def channels_status(user=Depends(current_user)):
    s = await get_settings(user["business_id"])''')
rep('''  var s = document.currentScript, origin = new URL(s.src).origin;''', '''  var s = document.currentScript, origin = new URL(s.src).origin;
  var biz = s.getAttribute('data-business') || 'default';''')
rep('''    f.src = origin + '/embed?site=' + encodeURIComponent(location.hostname);''', '''    f.src = origin + '/embed?b=' + encodeURIComponent(biz) + '&site=' + encodeURIComponent(location.hostname);''')

# ---- summary ----
rep('''    conv = await load_conv(cid)
    count = await db.messages.count_documents({"conversation_id": cid})''', '''    conv = await load_conv(cid, user["business_id"])
    count = await db.messages.count_documents({"conversation_id": cid})''')
rep('''        return None
    s = await get_settings()
    t = await transcript(cid, 40)''', '''        return None
    s = await get_settings(user["business_id"])
    t = await transcript(cid, 40)''')

# ---- startup ----
rep('''    await db.conversations.create_index([("channel", 1), ("external_id", 1)], unique=True)
    await db.messages.create_index("conversation_id")
    email, pw = os.environ['ADMIN_EMAIL'].lower(), os.environ['ADMIN_PASSWORD']
    existing = await db.users.find_one({"email": email})
    if not existing:
        await db.users.insert_one({"id": str(uuid.uuid4()), "email": email, "password_hash": hash_pw(pw), "name": "Admin", "role": "admin", "created_at": now_iso()})
    elif not verify_pw(pw, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_pw(pw)}})''', '''    try:
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
    logger.info("Migrated single-tenant data to business %s", bid)''')

rep('''from pymongo.errors import DuplicateKeyError''', '''from pymongo.errors import DuplicateKeyError, OperationFailure
import asyncio''')

open(p, 'w').write(s)
print("ok")
