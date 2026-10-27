# Iter27: final retest. Stub checks (IP-limit retry, store-link 3 tries), admin revenue in USD, preview without token_ok.
# Only test_preview_relay_live makes real KHQR.dev calls (~2). Never prints the token.
import os
import sys
import time
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
COLLS = ("settings", "conversations", "messages", "subscriptions", "invoices", "ai_usage", "media", "products", "orders")


@pytest.fixture
def clean(monkeypatch):
    monkeypatch.setattr(P, "KHQR", lambda *a, **k: object())
    P._calls.clear(); P._last.clear(); P._locks.clear(); P._store_currency.clear()
    yield
    P._calls.clear(); P._last.clear(); P._locks.clear(); P._store_currency.clear()


# --- stub: IP-limit retry succeeds; window sorted; background skipped during the pause
def test_ip_limit_retry_with_existing_entries(clean):
    now = time.time()
    P._calls.extend([now - 30, now - 20, now - 10])  # 3 real recent entries
    n = {"c": 0}
    seen = {}

    def fn(k):
        n["c"] += 1
        if n["c"] == 1:
            return_ = None  # noqa
            raise ValueError("IP Rate limit exceeded. Retry in 3s")
        return "OK"

    def bg():
        time.sleep(1.5)
        seen["bulk"] = P._bulk_paid("rbk_other", ["a" * 32])
        seen["sorted"] = list(P._calls) == sorted(P._calls)

    import threading
    th = threading.Thread(target=bg); th.start()
    t = time.time()
    assert P._relay_call("rbk_me", fn) == "OK"
    th.join()
    dt = time.time() - t
    assert n["c"] == 2 and 2.9 <= dt < 6, dt
    assert seen["bulk"] == [] and seen["sorted"] is True
    assert list(P._calls) == sorted(P._calls)
    assert len(P._calls) <= P._MAX


def test_ip_limit_retry_too_long_is_busy(clean):
    def fn(k):
        raise ValueError("IP Rate limit exceeded. Retry in 40s")
    t = time.time()
    with pytest.raises(ValueError, match="busy"):
        P._relay_call("rbk_me", fn, wait_max=25)
    assert time.time() - t < 3


# --- stub: store-link check retried up to 2 times (3 tries)
def test_store_link_third_try_succeeds(clean):
    n = {"c": 0}

    def fn(k):
        n["c"] += 1
        if n["c"] < 3:
            raise ValueError("Failed to validate store payment link.")
        return "OK"
    t = time.time()
    assert P._relay_call("rbk_a", fn) == "OK"
    dt = time.time() - t
    assert n["c"] == 3 and 4.9 <= dt < 8, dt


def test_store_link_three_failures_raise(clean):
    n = {"c": 0}

    def fn(k):
        n["c"] += 1
        raise ValueError("Failed to validate store payment link.")
    with pytest.raises(ValueError, match="validate store payment link"):
        P._relay_call("rbk_a", fn)
    assert n["c"] == 3


def test_store_link_no_retry_without_time(clean):
    n = {"c": 0}

    def fn(k):
        n["c"] += 1
        raise ValueError("Failed to validate store payment link.")
    with pytest.raises(ValueError):
        P._relay_call("rbk_a", fn, wait_max=2)
    assert n["c"] == 1


# --- live API
def _admin():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@replyflow.com", "password": "admin123"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def shop():
    stamp = uuid.uuid4().hex[:6]
    r = requests.post(f"{API}/auth/register", json={"email": f"test_i27_{stamp}@example.com", "password": "test12345",
                                                    "business_name": "TEST_i27shop"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    bid = d["user"]["business_id"]
    yield {"h": {"Authorization": f"Bearer {d['token']}"}, "bid": bid}
    for c in COLLS:
        DB[c].delete_many({"business_id": bid})
    DB.businesses.delete_one({"id": bid})
    DB.users.delete_many({"business_id": bid})


def test_public_plans():
    r = requests.get(f"{API}/public/plans", timeout=30)
    assert r.status_code == 200
    assert r.json()


def test_admin_revenue_usd(shop):
    bid = shop["bid"]
    DB.invoices.insert_many([
        {"id": f"TEST_{uuid.uuid4()}", "business_id": bid, "status": "paid", "amount": 41000, "currency": "KHR",
         "price_usd": 10, "md5": uuid.uuid4().hex},
        {"id": f"TEST_{uuid.uuid4()}", "business_id": bid, "status": "paid", "amount": 25, "currency": "USD",
         "md5": uuid.uuid4().hex},
        {"id": f"TEST_{uuid.uuid4()}", "business_id": bid, "status": "pending", "amount": 99, "currency": "USD",
         "price_usd": 99, "md5": uuid.uuid4().hex},
    ])
    r = requests.get(f"{API}/admin/businesses", headers=_admin(), timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    rows = data if isinstance(data, list) else data.get("businesses", data.get("items", []))
    row = next((x for x in rows if x.get("id") == bid or x.get("business_id") == bid), None)
    assert row, "test shop not in admin list"
    rev = row.get("revenue", (row.get("billing") or {}).get("revenue"))
    print("revenue:", rev)
    assert rev == 35.0


def test_preview_local_without_token(shop):
    DB.settings.update_one({"business_id": shop["bid"]}, {"$set": {"bakong_account_id": "test_i27@aclb", "khqr_token": ""}},
                           upsert=True)
    r = requests.post(f"{API}/payments/preview", headers=shop["h"], timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["mode"] == "local" and isinstance(d["media_id"], str) and d["deeplink"] is None


def test_preview_relay_live(shop):
    tok = (DB.settings.find_one({"business_id": VAA}, {"khqr_token": 1}) or {}).get("khqr_token", "")
    if not tok.startswith("rbk"):
        pytest.skip("no relay token")
    DB.settings.update_one({"business_id": shop["bid"]}, {"$set": {"khqr_token": tok, "bakong_account_id": ""}})
    t = time.time()
    r = requests.post(f"{API}/payments/preview", headers=shop["h"], timeout=120)
    print(f"relay preview: {r.status_code} in {time.time() - t:.1f}s {r.text[:200] if r.status_code != 200 else ''}")
    if r.status_code == 400 and "busy" in r.text.lower():
        pytest.skip("KHQR.dev busy (expected friendly message)")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["mode"] == "relay" and isinstance(d["media_id"], str)
    print("deeplink present:", bool(d.get("deeplink")))
