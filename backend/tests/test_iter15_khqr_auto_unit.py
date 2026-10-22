# Iteration 15: KHQR AUTOMATIC mode (relay mocked in-process) + deliver() KHQR Telegram/Messenger unit tests
import asyncio
import io
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

sys.path.insert(0, "/app/backend")
import server  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

BIZ = "TEST_biz_khqr_" + uuid.uuid4().hex[:6]
MD5 = "a" * 32
CALLS = {"bulk": 0}


def png_bytes():
    b = io.BytesIO()
    Image.new("RGB", (4, 4)).save(b, "PNG")
    return b.getvalue()


def run(coro_fn):
    async def wrap():
        server.db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        try:
            return await coro_fn()
        finally:
            await server.db.orders.delete_many({"business_id": BIZ})
            await server.db.messages.delete_many({"business_id": BIZ})
            await server.db.conversations.delete_many({"business_id": BIZ})
            await server.db.settings.delete_many({"business_id": BIZ})
    return asyncio.run(wrap())


@pytest.fixture(autouse=True)
def mocks(monkeypatch):
    CALLS["bulk"] = 0
    CALLS["mode"] = "second"

    async def make_qr(s, amount, currency, bill):
        return {"qr": "000201TEST", "md5": MD5, "mode": "relay", "png": png_bytes(), "deeplink": "https://bakong.page.link/x"}

    async def bulk_paid(token, md5s):
        CALLS["bulk"] += 1
        if CALLS["mode"] == "error":
            raise server.P.PaymentError("401 Unauthorized")
        return [MD5] if CALLS["bulk"] >= 2 and MD5 in md5s else []

    async def save_media(db, bid, data, ct, kind):
        return {"id": "TESTMEDIA_" + uuid.uuid4().hex[:6]}
    monkeypatch.setattr(server.P, "make_qr", make_qr)
    monkeypatch.setattr(server.P, "bulk_paid", bulk_paid)
    monkeypatch.setattr(server.M, "save_media", save_media)


async def setup():
    await server.db.settings.insert_one({"business_id": BIZ, "business_name": "TEST", "khqr_token": "rbk_test"})
    conv = {"id": "TESTCONV_" + uuid.uuid4().hex[:6], "business_id": BIZ, "channel": "web", "external_id": "x", "name": "TEST_c", "ai_enabled": True}
    await server.db.conversations.insert_one(dict(conv))
    await server.db.messages.insert_one({"id": uuid.uuid4().hex, "conversation_id": conv["id"], "business_id": BIZ, "role": "user",
                                         "text": "I want 2", "attachments": [], "created_at": server.now_iso()})
    s = await server.get_settings(BIZ)
    o = await server.create_order(conv, s, [({"id": "p1", "name": "Latte", "price": "2.5$"}, 2)])
    await server.add_message(conv, "ai", "Total $5.00", [server.khqr_att(o)])
    return conv, o


async def paid_msgs(conv):
    return await server.db.messages.count_documents({"conversation_id": conv["id"], "text": {"$regex": "^Payment received"}})


def test_auto_paid_idempotent():
    async def t():
        conv, o = await setup()
        assert o["mode"] == "relay" and o["total"] == 5.0 and o["currency"] == "USD"
        await server.poll_relay(late=False)  # 1st call -> not paid
        assert (await server.db.orders.find_one({"id": o["id"]}))["status"] == "pending"
        await server.poll_relay(late=False)  # 2nd call -> paid
        d = await server.db.orders.find_one({"id": o["id"]})
        assert d["status"] == "paid" and d["paid_by"] == "auto"
        for _ in range(3):
            await server.poll_relay(late=False)
            await server.poll_relay(late=True)
        assert await paid_msgs(conv) == 1
        m = await server.db.messages.find_one({"attachments.order_id": o["id"]})
        assert m["attachments"][0]["status"] == "paid"
        txt = (await server.db.messages.find_one({"conversation_id": conv["id"], "text": {"$regex": "^Payment received"}}))["text"]
        assert o["number"] in txt and "$5.00" in txt
    run(t)


def test_relay_error_keeps_pending():
    CALLS["mode"] = "error"

    async def t():
        conv, o = await setup()
        for _ in range(3):
            await server.poll_relay(late=False)
        assert (await server.db.orders.find_one({"id": o["id"]}))["status"] == "pending"
        assert await paid_msgs(conv) == 0
    run(t)


def test_late_payment_on_expired():
    async def t():
        conv, o = await setup()
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        await server.db.orders.update_one({"id": o["id"]}, {"$set": {"expires_at": past}})
        await server.expire_orders()
        assert (await server.db.orders.find_one({"id": o["id"]}))["status"] == "expired"
        CALLS["bulk"] = 1  # next call reports paid
        await server.poll_relay(late=False)  # expired not checked in normal poll
        assert (await server.db.orders.find_one({"id": o["id"]}))["status"] == "expired"
        await server.poll_relay(late=True)
        d = await server.db.orders.find_one({"id": o["id"]})
        assert d["status"] == "paid" and d["paid_by"] == "auto"
        assert await paid_msgs(conv) == 1
    run(t)


def test_late_ignores_old_orders():
    async def t():
        conv, o = await setup()
        old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        await server.db.orders.update_one({"id": o["id"]}, {"$set": {"status": "cancelled", "created_at": old}})
        CALLS["bulk"] = 5
        await server.poll_relay(late=True)
        assert (await server.db.orders.find_one({"id": o["id"]}))["status"] == "cancelled"
    run(t)


def test_second_order_cancels_previous():
    async def t():
        conv, o = await setup()
        s = await server.get_settings(BIZ)
        o2 = await server.create_order(conv, s, [({"id": "p1", "name": "Latte", "price": "2.5$"}, 3)])
        assert o2["total"] == 7.5
        assert (await server.db.orders.find_one({"id": o["id"]}))["status"] == "cancelled"
        assert (await server.db.messages.find_one({"attachments.order_id": o["id"]}))["attachments"][0]["status"] == "cancelled"
        o3 = await server.create_order(conv, s, [({"id": "p1", "name": "L", "price": "2.5$"}, 1), ({"id": "p2", "name": "K", "price": "15000៛"}, 1)])
        assert o3 is None
        assert (await server.db.orders.find_one({"id": o2["id"]}))["status"] == "pending"  # failed order must not cancel existing
    run(t)


# ---- deliver() with httpx mocked
SENT = []


class Resp:
    status_code, text = 200, "{}"


class FakeClient:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, **kw):
        SENT.append((url, kw))
        return Resp()


def order(deeplink=True):
    return {"id": "o", "qr_media_id": "q", "total": 5.0, "currency": "USD", "number": "RF-ABC123",
            "deeplink": "https://bakong.page.link/x" if deeplink else None}


@pytest.fixture
def fake_http(monkeypatch):
    SENT.clear()
    monkeypatch.setattr(server.httpx, "AsyncClient", FakeClient)

    async def load(db, mid):
        return (b"PNG" + mid.encode(), {"content_type": "image/png"})
    monkeypatch.setattr(server.M, "load_media", load)


@pytest.mark.parametrize("voice", [None, b"mp3"])
def test_deliver_telegram_khqr(fake_http, voice):
    conv = {"channel": "telegram", "external_id": "123"}
    prods = [{"id": "p", "name": "Latte", "price": "2.5$", "image_media_id": "m"}]
    asyncio.run(server.deliver(conv, server.Settings(telegram_token="tok"), "hi", voice, prods, order()))
    names = [u.rsplit("/", 1)[-1] for u, _ in SENT]
    assert names == (["sendMessage"] if voice is None else ["sendVoice"]) + ["sendPhoto", "sendPhoto"]
    kw = SENT[-1][1]
    assert kw["data"]["caption"].startswith("Bakong KHQR · $5.00 · Order RF-ABC123")
    assert "Pay with Bakong" in kw["data"]["reply_markup"] and kw["files"]["photo"][1] == b"PNGq"


def test_deliver_telegram_no_deeplink(fake_http):
    asyncio.run(server.deliver({"channel": "telegram", "external_id": "1"}, server.Settings(telegram_token="tok"), "hi", None, [], order(False)))
    assert "reply_markup" not in SENT[-1][1]["data"]


def test_deliver_messenger_khqr(fake_http):
    asyncio.run(server.deliver({"channel": "messenger", "external_id": "9"}, server.Settings(fb_page_token="fb"), "hi", None, [], order()))
    assert len(SENT) == 3  # text, image, caption
    assert SENT[1][1]["files"]["filedata"][0] == "khqr.png"
    assert '"image"' in SENT[1][1]["data"]["message"]
    cap = SENT[2][1]["json"]["message"]["text"]
    assert cap.startswith("Bakong KHQR · $5.00 · Order RF-ABC123") and "bakong.page.link" in cap
