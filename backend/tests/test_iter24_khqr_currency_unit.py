# Iter24: KHQR.dev KHR-only store currency conversion + per-token rate limiting (in-process, real KHQR.dev token)
import asyncio
import sys
import time
import uuid

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")
import pytest  # noqa: E402
from pymongo import MongoClient  # noqa: E402

import payments as P  # noqa: E402

VAA = "01cede8a-0348-4f28-bf35-707dfeb10235"
mc = MongoClient("mongodb://localhost:27017")["replyflow"]


def _settings():
    from core import Settings
    doc = mc.settings.find_one({"business_id": VAA}, {"_id": 0, "business_id": 0})
    if not doc or not (doc.get("khqr_token") or "").startswith("rbk"):
        pytest.skip("no relay token")
    return Settings(**{**doc, "business_name": "TEST_iter24"})


# convert(): pure math
def test_convert():
    assert P.convert(1.0, "USD", "KHR") == (4100.0, "KHR")
    assert P.convert(41000, "KHR", "USD") == (10.0, "USD")
    assert P.convert(25.0, "USD", "KHR") == (102500.0, "KHR")
    assert P.convert(5, "USD", "USD") == (5, "USD")
    assert P.convert(0.01, "USD", "KHR") == (100.0, "KHR")


# make_qr x2 + create_order = 3 QRs back to back (rate limit spacing / retry)
def test_relay_three_back_to_back():
    import orders as O
    from core import db
    s = _settings()
    bid = "TEST_iter24_" + uuid.uuid4().hex[:6]
    conv = {"id": "TEST_conv_" + uuid.uuid4().hex[:6], "business_id": bid, "channel": "telegram", "name": "TEST cust"}

    async def run():
        out = {}
        t = time.time()
        out["usd"] = await P.make_qr(s, 25.0, "USD", "RF-T24A")
        out["t1"] = time.time() - t
        t = time.time()
        out["khr"] = await P.make_qr(s, 40000, "KHR", "RF-T24B")
        out["t2"] = time.time() - t
        t = time.time()
        out["order"] = await O.create_order(conv, s, [({"id": "p1", "name": "TEST prod", "price": "25$"}, 1)])
        out["t3"] = time.time() - t
        await db.orders.delete_many({"business_id": bid})
        await db.media.delete_many({"business_id": bid})
        return out

    out = asyncio.run(run())
    print("timings", round(out["t1"], 2), round(out["t2"], 2), round(out["t3"], 2))
    u, k, o = out["usd"], out["khr"], out["order"]
    assert u["mode"] == "relay" and u["currency"] == "KHR" and u["amount"] == 102500.0
    assert u["qr"] and u["md5"] and u["png"]
    print("deeplink usd:", bool(u["deeplink"]), "khr:", bool(k["deeplink"]))
    assert k["mode"] == "relay" and k["currency"] == "KHR" and k["amount"] == 40000
    assert o is not None, "create_order returned None"
    assert o["total"] == 102500 and o["currency"] == "KHR"
    assert o["price_total"] == 25.0 and o["price_currency"] == "USD" and o["mode"] == "relay"
    cap = O.khqr_caption(o)
    print("caption:", cap.splitlines()[0])
    assert "102,500៛ ($25.00)" in cap
    assert mc.orders.count_documents({"business_id": conv["business_id"]}) == 0
