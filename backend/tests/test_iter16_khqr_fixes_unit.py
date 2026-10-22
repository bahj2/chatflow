# Iteration 16: unit checks — Khmer detection excludes riel sign/digits, QR_FAIL + PAID_MSG language, Khmer voice routing, RF-8hex numbers
import asyncio
import os
import re
import sys
import uuid

import pytest

sys.path.insert(0, "/app/backend")
import server  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

BIZ = "TEST_biz_khqr16_" + uuid.uuid4().hex[:6]


def run(coro_fn):
    async def wrap():
        server.db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        try:
            return await coro_fn()
        finally:
            for c in ("orders", "messages", "conversations", "settings"):
                await server.db[c].delete_many({"business_id": BIZ})
    return asyncio.run(wrap())


# ---- KHMER regex
def test_khmer_regex():
    K = server.M.KHMER
    assert not K.search("Your total is $2.5 + 15,000៛, scan the QR")
    assert not K.search("price ១២៣")
    assert K.search("ខ្ញុំចង់ទិញ ២ កែវ")
    assert K.search("សូមអរគុណ")


# ---- voice routing
def test_speak_routing(monkeypatch):
    calls = []

    async def hf(text, ref=None, ref_text="", timeout=60):
        calls.append(("hf", text))
        return b"MP3"

    class FakeTTS:
        def __init__(self, api_key=None):
            pass

        async def generate_speech(self, text, model, voice):
            calls.append(("openai", text))
            return b"OAI"
    monkeypatch.setattr(server.M, "hf_voxcpm", hf)
    monkeypatch.setattr(server.M, "OpenAITextToSpeech", FakeTTS)
    s = server.Settings(seller_voice_media_id="")
    _, eng = asyncio.run(server.M.speak(None, s, "សួស្តី តើអ្នកចង់ទិញអ្វី?"))
    assert eng == "voxcpm2-hf"
    _, eng2 = asyncio.run(server.M.speak(None, s, "Your total is 15,000៛"))
    assert eng2 == "openai"
    assert [c[0] for c in calls] == ["hf", "openai"]


async def mkconv(user_text):
    await server.db.settings.insert_one({"business_id": BIZ, "business_name": "TEST", "bakong_account_id": "test@aclb", "auto_reply": True})
    conv = {"id": "TESTCONV_" + uuid.uuid4().hex[:6], "business_id": BIZ, "channel": "web", "external_id": "x" + uuid.uuid4().hex[:4],
            "name": "TEST_c", "ai_enabled": True}
    await server.db.conversations.insert_one(dict(conv))
    await server.db.messages.insert_one({"id": uuid.uuid4().hex, "conversation_id": conv["id"], "business_id": BIZ, "role": "user",
                                         "text": user_text, "attachments": [], "created_at": server.now_iso()})
    return conv


# ---- PAID_MSG language with riel sign in English message
@pytest.mark.parametrize("txt,lang", [("I want 1 sandwich (15,000៛), confirmed", "en"), ("ខ្ញុំចង់ទិញ ១", "km")])
def test_paid_msg_lang(txt, lang):
    async def t():
        conv = await mkconv(txt)
        s = await server.get_settings(BIZ)
        o = await server.create_order(conv, s, [({"id": "p1", "name": "Sandwich", "price": "15000៛"}, 1)])
        assert re.fullmatch(r"RF-[0-9A-F]{8}", o["number"]), o["number"]
        assert await server.settle_order(o, "seller:test")
        m = await server.db.messages.find_one({"conversation_id": conv["id"], "role": "ai"}, sort=[("created_at", -1)])
        assert m["text"] == server.PAID_MSG[lang].format(number=o["number"], amount="15,000៛"), m["text"]
    run(t)


# ---- QR_FAIL language: English reply containing ៛ (mixed cart)
@pytest.mark.parametrize("reply,lang", [("Your total is $2.5 + 15,000៛. [[order:p1aaaa*1,p2bbbb*1]]", "en"),
                                        ("សរុប $2.5 + 15,000៛ [[order:p1aaaa*1,p2bbbb*1]]", "km")])
def test_qr_fail_lang(monkeypatch, reply, lang):
    prods = [{"id": "p1aaaa", "name": "Latte", "price": "2.5$"}, {"id": "p2bbbb", "name": "Sandwich", "price": "15000៛"}]

    async def gen(*a, **k):
        return reply

    async def lp(bid):
        return prods

    async def kn(*a, **k):
        return ""

    async def dl(*a, **k):
        return None
    monkeypatch.setattr(server, "generate_reply", gen)
    monkeypatch.setattr(server, "load_products", lp)
    monkeypatch.setattr(server.N, "knowledge", kn)
    monkeypatch.setattr(server, "deliver", dl)

    async def t():
        await server.db.settings.insert_one({"business_id": BIZ, "business_name": "TEST", "bakong_account_id": "test@aclb", "auto_reply": True})
        msg = await server.handle_incoming(BIZ, "web", "TEST_x" + uuid.uuid4().hex[:4], "TEST_c", "I want 1 latte and 1 sandwich")
        assert msg["text"].endswith(server.QR_FAIL[lang]), msg["text"]
        assert not [a for a in msg["attachments"] if a["type"] == "khqr"]
        assert await server.db.orders.count_documents({"business_id": BIZ}) == 0
    run(t)
