# Iteration 17: Website chat removal — widget endpoints 404, web data purged, stats w/o web, settings w/o greeting,
# Telegram/Messenger webhook regression (loadtest business with temporary fake creds), AI test order_total, mark-paid.
import hashlib
import hmac
import json
import os
import time
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
API = BASE_URL + "/api"
BID = "4f0dbc25-7fad-40f4-b898-0ef8db1d9799"
LT = ("loadtest+706ab4fd@example.com", "loadtest123")
ADMIN = ("admin@replyflow.com", "admin123")
env = {k: v.strip().strip('"') for k, v in (l.split("=", 1) for l in open("/app/backend/.env").read().splitlines() if "=" in l)}
mdb = MongoClient(env["MONGO_URL"])[env["DB_NAME"]]
JWT_SECRET = env["JWT_SECRET"]


def login(cred):
    r = requests.post(f"{API}/auth/login", json={"email": cred[0], "password": cred[1]}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def H():
    return login(LT)


@pytest.fixture(scope="module")
def AH():
    return login(ADMIN)


# ---- widget endpoints gone ----
@pytest.mark.parametrize("bid", ["default", BID])
def test_public_endpoints_404(bid):
    sid = "TEST_" + uuid.uuid4().hex[:6]
    calls = [
        ("get", f"{API}/public/{bid}/info", {}),
        ("post", f"{API}/public/{bid}/chat", {"json": {"session_id": sid, "text": "hi"}}),
        ("post", f"{API}/public/{bid}/voice", {"files": {"file": ("a.webm", b"xx", "audio/webm")}}),
        ("get", f"{API}/public/{bid}/chat/{sid}", {}),
    ]
    for m, url, kw in calls:
        r = getattr(requests, m)(url, timeout=30, **kw)
        assert r.status_code == 404, (url, r.status_code, r.text[:200])


def test_widget_js_404():
    r = requests.get(f"{API}/widget.js", timeout=30)
    assert r.status_code == 404, r.status_code


# ---- data purge ----
def test_no_web_data():
    assert mdb.conversations.count_documents({"channel": "web"}) == 0
    assert mdb.orders.count_documents({"channel": "web"}) == 0
    ids = mdb.conversations.distinct("id")
    assert mdb.messages.count_documents({"conversation_id": {"$nin": ids}}) == 0
    assert mdb.settings.count_documents({"greeting": {"$exists": True}}) == 0


# ---- stats ----
def test_stats_no_web(AH):
    r = requests.get(f"{API}/stats", headers=AH, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "web" not in d and isinstance(d["telegram"], int) and isinstance(d["messenger"], int)
    assert d["total"] >= d["telegram"] + d["messenger"]


# ---- settings ----
def test_settings_no_greeting(H):
    r = requests.get(f"{API}/settings", headers=H, timeout=30)
    assert r.status_code == 200 and "greeting" not in r.json()
    body = r.json()
    body["greeting"] = "legacy client value"  # old client sending removed field must not break
    r2 = requests.put(f"{API}/settings", headers=H, json=body, timeout=30)
    assert r2.status_code == 200, r2.text
    assert "greeting" not in r2.json()
    assert "greeting" not in requests.get(f"{API}/settings", headers=H, timeout=30).json()


def test_ai_test_order_total(H):
    r = requests.post(f"{API}/ai/test", headers=H, json={"text": "I want to buy 2 Iced Palm Sugar Latte, confirmed, how do I pay?"}, timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    print("AI test:", d)
    assert d["reply"] and "order_total" in d


# ---- webhook regression with temporary fake creds on loadtest ----
@pytest.fixture(scope="module")
def creds(H):
    orig = requests.get(f"{API}/settings", headers=H, timeout=30).json()
    tmp = dict(orig, telegram_token="TEST_FAKE:" + uuid.uuid4().hex, fb_app_secret="TEST_secret_" + uuid.uuid4().hex[:8])
    assert requests.put(f"{API}/settings", headers=H, json=tmp, timeout=30).status_code == 200
    yield tmp
    restore = requests.get(f"{API}/settings", headers=H, timeout=30).json()
    restore.update(telegram_token=orig["telegram_token"], fb_app_secret=orig["fb_app_secret"])
    requests.put(f"{API}/settings", headers=H, json=restore, timeout=30)


def wait_ai(channel, ext, n=1, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        c = mdb.conversations.find_one({"business_id": BID, "channel": channel, "external_id": ext})
        if c:
            ai = list(mdb.messages.find({"conversation_id": c["id"], "role": "ai"}, {"_id": 0}).sort("created_at", 1))
            if len(ai) >= n:
                return c, ai
        time.sleep(3)
    return None, []


def test_telegram_webhook_bad_secret(creds):
    r = requests.post(f"{API}/webhooks/telegram/{BID}", json={"message": {}}, headers={"X-Telegram-Bot-Api-Secret-Token": "nope"}, timeout=30)
    assert r.status_code == 403


def test_telegram_webhook_ai_reply(creds):
    chat_id = int(time.time())  # fake chat
    upd = {"update_id": 1, "message": {"message_id": 1, "chat": {"id": chat_id, "type": "private"},
                                        "from": {"id": chat_id, "first_name": "TEST_TG"}, "text": "What are your opening hours?"}}
    sec = hashlib.sha256(f"{JWT_SECRET}:{BID}:{creds['telegram_token']}".encode()).hexdigest()
    r = requests.post(f"{API}/webhooks/telegram/{BID}", json=upd, headers={"X-Telegram-Bot-Api-Secret-Token": sec}, timeout=30)
    assert r.status_code == 200 and r.json() == {"ok": True}
    c, ai = wait_ai("telegram", str(chat_id))
    assert c and ai and ai[0]["text"], "no AI reply stored for telegram conv"
    print("TG AI:", ai[0]["text"][:200])
    mdb.messages.delete_many({"conversation_id": c["id"]})
    mdb.conversations.delete_one({"id": c["id"]})


def test_messenger_bad_sig(creds):
    r = requests.post(f"{API}/webhooks/messenger/{BID}", data=b"{}", headers={"X-Hub-Signature-256": "sha256=00", "Content-Type": "application/json"}, timeout=30)
    assert r.status_code == 403


def test_messenger_order_and_mark_paid(creds, H):
    psid = "TEST" + uuid.uuid4().hex[:10]
    body = json.dumps({"object": "page", "entry": [{"messaging": [{"sender": {"id": psid}, "recipient": {"id": "1"},
                       "message": {"mid": "m1", "text": "I want to buy 2 Iced Palm Sugar Latte, confirmed, how do I pay?"}}]}]}).encode()
    sig = "sha256=" + hmac.new(creds["fb_app_secret"].encode(), body, hashlib.sha256).hexdigest()
    r = requests.post(f"{API}/webhooks/messenger/{BID}", data=body, headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"}, timeout=30)
    assert r.status_code == 200
    c, ai = wait_ai("messenger", psid)
    assert c and ai, "no AI reply stored for messenger conv"
    print("MSG AI:", ai[0]["text"][:300], [a["type"] for a in ai[0].get("attachments", [])])
    orders = requests.get(f"{API}/orders", headers=H, timeout=30)
    assert orders.status_code == 200 and isinstance(orders.json(), list)
    mine = [o for o in orders.json() if o["conversation_id"] == c["id"]]
    try:
        assert mine, "AI did not create an order for messenger latte purchase"
        o = mine[0]
        assert o["channel"] == "messenger" and o["status"] == "pending" and "qr" not in o and "md5" not in o
        r = requests.post(f"{API}/orders/{o['id']}/mark-paid", headers=H, timeout=30)
        assert r.status_code == 200 and r.json()["status"] == "paid", r.text
        r2 = requests.post(f"{API}/orders/{o['id']}/mark-paid", headers=H, timeout=30)
        assert r2.status_code == 409
        last = mdb.messages.find_one({"conversation_id": c["id"], "role": "ai"}, sort=[("created_at", -1)])
        assert last["text"].startswith("Payment received") and o["number"] in last["text"]
    finally:
        mdb.orders.delete_many({"conversation_id": c["id"]})
        mdb.messages.delete_many({"conversation_id": c["id"]})
        mdb.conversations.delete_one({"id": c["id"]})


def test_conversations_filter_web_empty(H):
    r = requests.get(f"{API}/conversations", headers=H, params={"channel": "web"}, timeout=30)
    assert r.status_code == 200 and r.json()["total"] == 0
