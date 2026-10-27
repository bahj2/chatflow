# Iter25: follow-ups to iter24 - store-currency memory in _relay_any, invoice matches QR (billing.checkout)
import asyncio
import sys
import uuid

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")
import pytest  # noqa: E402
from pymongo import MongoClient  # noqa: E402

import payments as P  # noqa: E402

VAA = "01cede8a-0348-4f28-bf35-707dfeb10235"
mc = MongoClient("mongodb://localhost:27017")["replyflow"]


def _settings(**extra):
    from core import Settings
    doc = mc.settings.find_one({"business_id": VAA}, {"_id": 0, "business_id": 0})
    if not doc or not (doc.get("khqr_token") or "").startswith("rbk"):
        pytest.skip("no relay token")
    return Settings(**{**doc, "business_name": "TEST_iter25", **extra})


# FOLLOW-UP 1: the 2nd QR for a KHR-only token must not make a failing USD attempt first
def test_store_currency_memory(monkeypatch):
    s = _settings()
    P._store_currency.clear()
    calls = []
    real = P._relay_qr

    def counting(token, amount, currency, bill):
        calls.append((amount, currency))
        return real(token, amount, currency, bill)

    monkeypatch.setattr(P, "_relay_qr", counting)

    async def run():
        a = await P.make_qr(s, 1.0, "USD", "RF-T25A")
        n1 = len(calls)
        b = await P.make_qr(s, 1.0, "USD", "RF-T25B")
        return a, n1, b

    a, n1, b = asyncio.run(run())
    print("calls", calls)
    assert n1 == 2, calls
    assert len(calls) - n1 == 1, calls
    assert calls[-1] == (4100.0, "KHR")
    assert (a["amount"], a["currency"]) == (4100.0, "KHR")
    assert (b["amount"], b["currency"]) == (4100.0, "KHR")
    assert a["mode"] == b["mode"] == "relay"
    assert P._store_currency.get(s.khqr_token.strip()) == "KHR"


# FOLLOW-UP 2: invoice stores QR amount/currency + price_usd; founder local mode still 10 USD
def test_checkout_invoice_matches_qr():
    import billing as B
    from core import db, platform_settings
    ps_rbk = _settings(bakong_account_id="tit_sambath@bkrt")
    bid1 = "TEST_iter25_" + uuid.uuid4().hex[:6]
    bid2 = "TEST_iter25_" + uuid.uuid4().hex[:6]

    async def run():
        try:
            inv1 = await B.checkout(db, bid1, "starter", ps_rbk)
            stored1 = await db.invoices.find_one({"id": inv1["id"]}, {"_id": 0})
            ps = await platform_settings()
            inv2 = await B.checkout(db, bid2, "starter", ps)
            stored2 = await db.invoices.find_one({"id": inv2["id"]}, {"_id": 0})
            return inv1, stored1, inv2, stored2, ps
        finally:
            for b in (bid1, bid2):
                await db.invoices.delete_many({"business_id": b})
                await db.subscriptions.delete_many({"business_id": b})
                await db.businesses.delete_many({"id": b})

    inv1, s1, inv2, s2, ps = asyncio.run(run())
    print("rbk invoice", {k: s1.get(k) for k in ("amount", "currency", "price_usd", "mode")})
    print("founder invoice", {k: s2.get(k) for k in ("amount", "currency", "price_usd", "mode")})
    assert s1["amount"] == 41000.0 and s1["currency"] == "KHR" and s1["price_usd"] == 10.0
    assert s1["mode"] == "relay"
    assert inv1.get("amount") == 41000.0 and inv1.get("currency") == "KHR"
    assert s2["amount"] == 10.0 and s2["currency"] == "USD" and s2["price_usd"] == 10.0
    assert not (ps.khqr_token or "").startswith("rbk")
    assert mc.invoices.count_documents({"business_id": {"$in": [bid1, bid2]}}) == 0
