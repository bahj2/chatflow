# Iter26 LIVE: KHR-only KHQR.dev token copied into a new test shop. preview 2/2, make_qr 25 USD -> 102500 KHR.
# Uses ~10 real KHQR.dev calls. Wait ~60 s before running; never prints the token.
import asyncio
import os
import sys
import time
import types
import uuid

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
import payments as P  # noqa: E402

API = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
VAA = "01cede8a-0348-4f28-bf35-707dfeb10235"
STAMP = uuid.uuid4().hex[:6]
COLLS = ("settings", "conversations", "messages", "subscriptions", "invoices", "ai_usage", "media", "products", "orders")


def _tok():
    return (DB.settings.find_one({"business_id": VAA}, {"khqr_token": 1}) or {}).get("khqr_token", "")


@pytest.fixture(scope="module")
def shop():
    tok = _tok()
    if not tok.startswith("rbk"):
        pytest.skip("no relay token")
    DB.rate_hits.delete_many({})
    r = requests.post(f"{API}/auth/register", json={"email": f"test_i26_{STAMP}@example.com", "password": "test12345",
                                                    "business_name": f"TEST_i26shop"})
    assert r.status_code == 200, r.text
    d = r.json()
    bid = d["user"]["business_id"]
    DB.settings.update_one({"business_id": bid}, {"$set": {"khqr_token": tok}}, upsert=True)
    yield {"tok": d["token"], "bid": bid}
    for c in COLLS:
        DB[c].delete_many({"business_id": bid})
    DB.businesses.delete_one({"id": bid})
    DB.users.delete_many({"business_id": bid})


@pytest.mark.parametrize("n", [1, 2])
def test_preview_live(shop, n):
    if n == 2:
        time.sleep(8)
    t = time.time()
    r = requests.post(f"{API}/payments/preview", headers={"Authorization": f"Bearer {shop['tok']}"}, timeout=120)
    print(f"preview {n}: {r.status_code} in {time.time() - t:.1f}s {r.text[:200] if r.status_code != 200 else ''}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["mode"] == "relay" and isinstance(d["media_id"], str)
    print("deeplink present:", bool(d.get("deeplink")))


def test_make_qr_25usd_is_102500khr(shop):
    time.sleep(5)
    s = types.SimpleNamespace(khqr_token=_tok(), business_name="TEST_i26shop", bakong_account_id="", bakong_merchant_name="",
                              bakong_city="")
    q = asyncio.run(P.make_qr(s, 25.0, "USD", f"RFT{STAMP}"))
    print("make_qr:", q["amount"], q["currency"], q["mode"], "deeplink:", bool(q["deeplink"]), "budget used:", len(P._calls))
    assert q["currency"] == "KHR" and q["amount"] == 102500
    assert q["mode"] == "relay" and q["png"][:4] == b"\x89PNG" and len(q["md5"]) == 32
