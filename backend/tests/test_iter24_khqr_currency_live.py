# Iter24 live API: KHR-only KHQR.dev preview, local preview regression, founder billing checkout, token validation
import base64
import json
import os
import uuid

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
API = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
VAA = "01cede8a-0348-4f28-bf35-707dfeb10235"
STAMP = uuid.uuid4().hex[:6]
COLLS = ("settings", "conversations", "messages", "subscriptions", "invoices", "ai_usage", "media", "products", "orders")


def H(t):
    return {"Authorization": f"Bearer {t}"}


def register(tag):
    r = requests.post(f"{API}/auth/register", json={"email": f"test_i24{tag}_{STAMP}@example.com", "password": "test12345",
                                                    "business_name": f"TEST_i24{tag}"})
    assert r.status_code == 200, r.text
    d = r.json()
    return {"tok": d["token"], "bid": d["user"]["business_id"]}


def cleanup(bid):
    for c in COLLS:
        DB[c].delete_many({"business_id": bid})
    DB.businesses.delete_one({"id": bid})
    DB.users.delete_many({"business_id": bid})


@pytest.fixture(scope="module")
def khr_shop():
    s = register("khr")
    tok = (DB.settings.find_one({"business_id": VAA}, {"khqr_token": 1}) or {}).get("khqr_token", "")
    if not tok.startswith("rbk"):
        pytest.skip("no relay token")
    DB.settings.update_one({"business_id": s["bid"]}, {"$set": {"khqr_token": tok, "bakong_account_id": "tit_sambath@bkrt"}}, upsert=True)
    yield s
    cleanup(s["bid"])


@pytest.fixture(scope="module")
def local_shop():
    s = register("loc")
    yield s
    cleanup(s["bid"])


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@replyflow.com", "password": "admin123"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["user"]["role"] == "superadmin"
    return {"tok": d["token"]}


# BUG FIX 1: $1 preview on a KHR-only KHQR.dev store
def test_preview_khr_store_relay(khr_shop):
    r = requests.post(f"{API}/payments/preview", headers=H(khr_shop["tok"]), timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["mode"] == "relay" and isinstance(d["media_id"], str)
    print("deeplink present:", bool(d.get("deeplink")))
    m = requests.get(f"{API}/media/{d['media_id']}")
    assert m.status_code == 200 and m.content[:4] == b"\x89PNG"


# REGRESSION: account-only shop -> local QR
def test_preview_local(local_shop):
    h = H(local_shop["tok"])
    cur = requests.get(f"{API}/settings", headers=h).json()
    r = requests.put(f"{API}/settings", headers=h, json={**cur, "bakong_account_id": "tit_sambath@bkrt", "khqr_token": ""})
    assert r.status_code == 200, r.text
    p = requests.post(f"{API}/payments/preview", headers=h, timeout=60)
    assert p.status_code == 200, p.text
    assert p.json()["mode"] == "local"


# REGRESSION: normal shop cannot save an eyJ token
def test_shop_eyj_rejected(local_shop):
    h = H(local_shop["tok"])
    cur = requests.get(f"{API}/settings", headers=h).json()
    r = requests.put(f"{API}/settings", headers=h, json={**cur, "khqr_token": "eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjF9.x"})
    assert r.status_code == 400 and "rbk" in r.json()["detail"]


# REGRESSION: founder expired Bakong token rejected
def test_founder_expired_token(admin):
    h = H(admin["tok"])
    cur = requests.get(f"{API}/settings", headers=h).json()
    pl = base64.urlsafe_b64encode(json.dumps({"exp": 1700000000}).encode()).decode().rstrip("=")
    bad = f"eyJhbGciOiJIUzI1NiJ9.{pl}.sig"
    r = requests.put(f"{API}/settings", headers=h, json={**cur, "khqr_token": bad})
    assert r.status_code == 400, r.text
    assert "expired on" in r.json()["detail"]


# REGRESSION: founder billing checkout -> $10 Starter, QR with tit_sambath@bkrt
def test_billing_checkout(local_shop):
    r = requests.post(f"{API}/billing/checkout", headers=H(local_shop["tok"]), json={"item": "starter"}, timeout=60)
    assert r.status_code == 200, r.text
    inv = r.json()
    assert inv["amount"] == 10.0 and inv["currency"] == "USD" and inv["status"] == "pending"
    print("invoice mode:", inv["mode"])
    doc = DB.invoices.find_one({"id": inv["id"]}, {"_id": 0, "qr": 1})
    assert "tit_sambath@bkrt" in doc["qr"]
