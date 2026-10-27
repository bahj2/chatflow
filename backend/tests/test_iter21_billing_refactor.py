"""Iteration 21: regression after server.py module split + subscriptions/billing + Pro gating + admin plan endpoints."""
# Run serially: pytest tests/test_iter21_billing_refactor.py -n 0  (module fixtures share shops across classes)
import io
import os
import time
import uuid

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
STAMP = uuid.uuid4().hex[:6]
COLLS = ("settings", "conversations", "messages", "subscriptions", "invoices", "ai_usage", "media", "products", "orders", "notion_links", "notion_docs")


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def register(tag):
    r = requests.post(f"{API}/auth/register", json={"email": f"test_{tag}_{STAMP}@example.com", "password": "test12345", "business_name": f"TEST_{tag}"})
    assert r.status_code == 200, r.text
    d = r.json()
    return {"tok": d["token"], "bid": d["user"]["business_id"], "email": d["user"]["email"]}


def cleanup(bid):
    for c in COLLS:
        DB[c].delete_many({"business_id": bid})
    DB.businesses.delete_one({"id": bid})
    DB.users.delete_many({"business_id": bid})


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@replyflow.com", "password": "admin123"})
    assert r.status_code == 200, r.text
    d = r.json()
    orig = requests.get(f"{API}/settings", headers=H(d["token"])).json()
    yield {"tok": d["token"], "bid": d["user"]["business_id"], "orig": orig}
    requests.put(f"{API}/settings", headers=H(d["token"]), json=orig)


@pytest.fixture(scope="module")
def shop_a():
    s = register("a")
    yield s
    cleanup(s["bid"])


@pytest.fixture(scope="module")
def shop_b():
    s = register("b")
    yield s
    cleanup(s["bid"])


@pytest.fixture(scope="module")
def conv_a(shop_a):
    cid = str(uuid.uuid4())
    t = "2026-01-10T10:00:00+00:00"
    DB.conversations.insert_one({"id": cid, "business_id": shop_a["bid"], "channel": "telegram", "external_id": f"ext{STAMP}", "name": "TEST cust",
                                 "ai_enabled": True, "unread": 1, "last_message": "Hi", "created_at": t, "updated_at": t})
    DB.messages.insert_one({"id": str(uuid.uuid4()), "conversation_id": cid, "business_id": shop_a["bid"], "role": "user",
                            "text": "Hello, do you deliver to Siem Reap? How much is the coffee?", "attachments": [], "created_at": t})
    return cid


# ---------- Auth ----------
class TestAuth:
    def test_login_bad(self):
        r = requests.post(f"{API}/auth/login", json={"email": "admin@replyflow.com", "password": "nope_wrong"})
        assert r.status_code == 401

    def test_me(self, admin):
        r = requests.get(f"{API}/auth/me", headers=H(admin["tok"]))
        assert r.status_code == 200 and r.json()["role"] == "superadmin"

    def test_me_noauth(self):
        assert requests.get(f"{API}/auth/me").status_code == 401


# ---------- Regression: settings / conversations / shop ----------
class TestRegression:
    def test_settings_get_put(self, shop_a):
        cur = requests.get(f"{API}/settings", headers=H(shop_a["tok"])).json()
        assert cur["business_name"] == "TEST_a"
        r = requests.put(f"{API}/settings", headers=H(shop_a["tok"]), json={**cur, "assistant_name": "TEST_Seller", "greeting": "TEST hi"})
        assert r.status_code == 200, r.text
        got = requests.get(f"{API}/settings", headers=H(shop_a["tok"])).json()
        assert got["assistant_name"] == "TEST_Seller" and got["greeting"] == "TEST hi"

    def test_duplicate_telegram_409(self, shop_a, shop_b):
        tok = f"77{STAMP[:4]}1:AAFAKE"
        ca = requests.get(f"{API}/settings", headers=H(shop_a["tok"])).json()
        r = requests.put(f"{API}/settings", headers=H(shop_a["tok"]), json={**ca, "telegram_token": tok})
        assert r.status_code == 200, r.text
        cb = requests.get(f"{API}/settings", headers=H(shop_b["tok"])).json()
        r = requests.put(f"{API}/settings", headers=H(shop_b["tok"]), json={**cb, "telegram_token": tok.replace("AAFAKE", "BBOTHER")})
        assert r.status_code == 409

    def test_team_limit_402_trial(self, shop_a):
        cur = requests.get(f"{API}/settings", headers=H(shop_a["tok"])).json()
        r = requests.put(f"{API}/settings", headers=H(shop_a["tok"]), json={**cur, "allowed_emails": ["mate1@example.com"]})
        assert r.status_code == 402

    def test_conversations_flow(self, shop_a, conv_a):
        r = requests.get(f"{API}/conversations", headers=H(shop_a["tok"]))
        assert r.status_code == 200 and r.json()["total"] == 1
        assert requests.get(f"{API}/conversations/{conv_a}/messages", headers=H(shop_a["tok"])).status_code == 200
        p = requests.patch(f"{API}/conversations/{conv_a}", headers=H(shop_a["tok"]), json={"unread": 0})
        assert p.status_code == 200 and p.json()["unread"] == 0
        rp = requests.post(f"{API}/conversations/{conv_a}/reply", headers=H(shop_a["tok"]), json={"text": "TEST manual"})
        assert rp.status_code == 200 and rp.json()["role"] == "agent"

    def test_other_shop_conv_404(self, shop_b, conv_a):
        assert requests.get(f"{API}/conversations/{conv_a}/messages", headers=H(shop_b["tok"])).status_code == 404

    def test_suggest_trial_200(self, shop_a, conv_a):
        r = requests.post(f"{API}/conversations/{conv_a}/suggest", headers=H(shop_a["tok"]), timeout=90)
        assert r.status_code == 200, r.text
        assert len(r.json()["suggestions"]) >= 1

    def test_summary_trial_200(self, shop_a, conv_a):
        r = requests.post(f"{API}/conversations/{conv_a}/summary", headers=H(shop_a["tok"]), timeout=90)
        assert r.status_code == 200, r.text
        assert r.json()["summary"]

    def test_ai_test(self, shop_a):
        r = requests.post(f"{API}/ai/test", headers=H(shop_a["tok"]), json={"text": "Hi, are you open today?"}, timeout=90)
        assert r.status_code == 200, r.text
        assert r.json()["reply"]

    def test_products_crud_and_image(self, shop_a):
        png = DB.media.find_one({}) and None
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), "red").save(buf, "PNG")
        up = requests.post(f"{API}/media/image", headers=H(shop_a["tok"]), files={"file": ("p.png", buf.getvalue(), "image/png")})
        assert up.status_code == 200, up.text
        mid = up.json()["id"]
        assert requests.get(f"{API}/media/{mid}").status_code == 200
        c = requests.post(f"{API}/products", headers=H(shop_a["tok"]), json={"name": "TEST Latte", "price": "$2", "image_media_id": mid})
        assert c.status_code == 200
        pid = c.json()["id"]
        u = requests.put(f"{API}/products/{pid}", headers=H(shop_a["tok"]), json={"name": "TEST Latte L", "price": "$3"})
        assert u.status_code == 200 and u.json()["name"] == "TEST Latte L"
        lst = requests.get(f"{API}/products", headers=H(shop_a["tok"])).json()
        assert any(p["id"] == pid for p in lst)
        assert requests.delete(f"{API}/products/{pid}", headers=H(shop_a["tok"])).status_code == 200
        assert requests.delete(f"{API}/products/{pid}", headers=H(shop_a["tok"])).status_code == 404
        assert png is None

    def test_orders_and_preview(self, shop_a):
        assert requests.get(f"{API}/orders", headers=H(shop_a["tok"])).status_code == 200
        assert requests.post(f"{API}/orders/nope/mark-paid", headers=H(shop_a["tok"])).status_code == 404
        assert requests.post(f"{API}/orders/nope/cancel", headers=H(shop_a["tok"])).status_code == 404
        assert requests.post(f"{API}/payments/preview", headers=H(shop_a["tok"])).status_code == 400

    def test_misc_gets(self, shop_a):
        for p in ("notion", "channels/status", "stats"):
            r = requests.get(f"{API}/{p}", headers=H(shop_a["tok"]))
            assert r.status_code == 200, (p, r.text)
        assert requests.get(f"{API}/notion", headers=H(shop_a["tok"])).json()["connected"] is False

    def test_webhooks_403(self, shop_a):
        assert requests.post(f"{API}/webhooks/telegram/{shop_a['bid']}", json={}, headers={"X-Telegram-Bot-Api-Secret-Token": "bad"}).status_code == 403
        assert requests.get(f"{API}/webhooks/messenger/{shop_a['bid']}", params={"hub.mode": "subscribe", "hub.verify_token": "x"}).status_code == 403


# ---------- Pro gating ----------
class TestProGating:
    def test_trial_gated(self, shop_b):
        b = requests.get(f"{API}/billing", headers=H(shop_b["tok"])).json()
        assert b["sub"]["plan"] == "trial" and b["sub"]["pro"] is False and b["sub"]["team"] == 1 and b["sub"]["limit"] == 200
        h = H(shop_b["tok"])
        assert requests.post(f"{API}/voice/test", headers=h, json={"text": "hello"}).status_code == 402
        assert requests.post(f"{API}/notion/connect", headers=h, json={"token": "ntn_abcdefghijklmnop"}).status_code == 402
        assert requests.post(f"{API}/notion/sync", headers=h).status_code == 402
        assert requests.post(f"{API}/settings/seller-voice", headers=h, files={"file": ("a.wav", b"xxxx", "audio/wav")}).status_code == 402

    def test_set_plan_pro_unlocks(self, admin, shop_b):
        r = requests.post(f"{API}/admin/businesses/{shop_b['bid']}/plan", headers=H(admin["tok"]), json={"plan": "pro", "days": 30})
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["plan"] == "pro" and s["pro"] is True and s["limit"] == 3000 and s["used"] == 0 and s["team"] == 3
        h = H(shop_b["tok"])
        assert requests.post(f"{API}/notion/sync", headers=h).status_code == 400  # "Connect Notion first", not 402
        assert requests.post(f"{API}/notion/connect", headers=h, json={"token": "ntn_abcdefghijklmnop"}).status_code == 400
        assert requests.post(f"{API}/settings/seller-voice", headers=h, files={"file": ("a.wav", b"xxxx", "audio/wav")}).status_code == 400
        vt = requests.post(f"{API}/voice/test", headers=h, json={"text": "hello"}, timeout=90)
        assert vt.status_code in (200, 424), vt.text

    def test_pro_team_limit(self, shop_b):
        cur = requests.get(f"{API}/settings", headers=H(shop_b["tok"])).json()
        r = requests.put(f"{API}/settings", headers=H(shop_b["tok"]), json={**cur, "allowed_emails": ["m1@example.com", "m2@example.com"]})
        assert r.status_code == 200, r.text
        r = requests.put(f"{API}/settings", headers=H(shop_b["tok"]), json={**cur, "allowed_emails": ["m1@example.com", "m2@example.com", "m3@example.com"]})
        assert r.status_code == 402

    def test_set_plan_extend_same(self, admin, shop_b):
        before = requests.get(f"{API}/billing", headers=H(shop_b["tok"])).json()["sub"]
        r = requests.post(f"{API}/admin/businesses/{shop_b['bid']}/plan", headers=H(admin["tok"]), json={"plan": "pro", "days": 10})
        assert r.status_code == 200
        assert r.json()["days_left"] == before["days_left"] + 10

    def test_set_plan_errors(self, admin, shop_a):
        a = H(admin["tok"])
        assert requests.post(f"{API}/admin/businesses/{admin['bid']}/plan", headers=a, json={"plan": "pro", "days": 30}).status_code == 400
        assert requests.post(f"{API}/admin/businesses/nope-{STAMP}/plan", headers=a, json={"plan": "pro", "days": 30}).status_code == 404
        assert requests.post(f"{API}/admin/businesses/{shop_a['bid']}/plan", headers=a, json={"plan": "gold", "days": 30}).status_code == 422
        assert requests.post(f"{API}/admin/businesses/{shop_a['bid']}/plan", headers=a, json={"plan": "pro", "days": 0}).status_code == 422
        assert requests.post(f"{API}/admin/businesses/{shop_a['bid']}/plan", headers=a, json={"plan": "pro", "days": 367}).status_code == 422
        assert requests.post(f"{API}/admin/businesses/{shop_a['bid']}/plan", headers=H(shop_a["tok"]), json={"plan": "pro", "days": 30}).status_code == 403


# ---------- Billing / invoices ----------
class TestBilling:
    def test_billing_shape(self, shop_a):
        b = requests.get(f"{API}/billing", headers=H(shop_a["tok"])).json()
        for k in ("sub", "plans", "topup", "payments_ready", "auto_confirm", "invoices"):
            assert k in b
        for k in ("plan", "used", "limit", "pro", "team", "paused", "reason"):
            assert k in b["sub"]
        assert [p["key"] for p in b["plans"]] == ["starter", "pro", "business"]
        assert b["topup"] == {"replies": 1000, "price": 5}

    def test_checkout_no_bakong_503(self, admin, shop_a):
        requests.put(f"{API}/settings", headers=H(admin["tok"]), json={**admin["orig"], "bakong_account_id": "", "khqr_token": ""})
        r = requests.post(f"{API}/billing/checkout", headers=H(shop_a["tok"]), json={"item": "starter"})
        assert r.status_code == 503

    def test_checkout_flow(self, admin, shop_a, shop_b):
        r = requests.put(f"{API}/settings", headers=H(admin["tok"]), json={**admin["orig"], "bakong_account_id": "replyflow@aclb", "bakong_merchant_name": "Replyflow AI"})
        assert r.status_code == 200, r.text
        h = H(shop_a["tok"])
        assert requests.get(f"{API}/billing", headers=h).json()["payments_ready"] is True
        assert requests.post(f"{API}/billing/checkout", headers=h, json={"item": "topup"}).status_code == 400
        assert requests.post(f"{API}/billing/checkout", headers=h, json={"item": "gold"}).status_code == 400
        inv = requests.post(f"{API}/billing/checkout", headers=h, json={"item": "starter"})
        assert inv.status_code == 200, inv.text
        inv = inv.json()
        assert inv["status"] == "pending" and inv["mode"] == "local" and inv["amount"] == 10.0
        again = requests.post(f"{API}/billing/checkout", headers=h, json={"item": "starter"}).json()
        assert again["id"] == inv["id"]
        q = requests.get(f"{API}/billing/invoices/{inv['id']}/qr.png")
        assert q.status_code == 200 and q.headers["content-type"] == "image/png" and q.content[:4] == b"\x89PNG"
        assert requests.get(f"{API}/billing/invoices/nope/qr.png").status_code == 404
        g = requests.get(f"{API}/billing/invoices/{inv['id']}", headers=h)
        assert g.status_code == 200 and g.json()["id"] == inv["id"]
        assert requests.get(f"{API}/billing/invoices/{inv['id']}", headers=H(shop_b["tok"])).status_code == 404
        assert "qr" not in g.json() and "md5" not in g.json()
        # admin lists & confirms
        pend = requests.get(f"{API}/admin/invoices", headers=H(admin["tok"])).json()
        assert any(i["id"] == inv["id"] and i["business_name"] == "TEST_a" for i in pend)
        assert requests.post(f"{API}/admin/invoices/{inv['id']}/confirm", headers=h).status_code == 403
        c = requests.post(f"{API}/admin/invoices/{inv['id']}/confirm", headers=H(admin["tok"]))
        assert c.status_code == 200, c.text
        s = c.json()["sub"]
        assert c.json()["status"] == "paid" and s["plan"] == "starter" and s["limit"] == 1000 and s["used"] == 0 and s["pro"] is False
        assert requests.post(f"{API}/admin/invoices/{inv['id']}/confirm", headers=H(admin["tok"])).status_code == 409
        # starter still gated
        assert requests.post(f"{API}/notion/sync", headers=h).status_code == 402
        # topup now allowed
        t = requests.post(f"{API}/billing/checkout", headers=h, json={"item": "topup"})
        assert t.status_code == 200 and t.json()["amount"] == 5.0
        ct = requests.post(f"{API}/admin/invoices/{t.json()['id']}/confirm", headers=H(admin["tok"])).json()
        assert ct["sub"]["extra"] == 1000

    def test_admin_checkout_400(self, admin):
        assert requests.post(f"{API}/billing/checkout", headers=H(admin["tok"]), json={"item": "starter"}).status_code == 400

    def test_admin_invoices_403_for_owner(self, shop_a):
        assert requests.get(f"{API}/admin/invoices", headers=H(shop_a["tok"])).status_code == 403


# ---------- Admin businesses ----------
class TestAdminBusinesses:
    def test_rows_have_billing(self, admin, shop_a):
        DB.subscriptions.delete_one({"business_id": shop_a["bid"]})  # simulate an old shop with no subscription
        r = requests.get(f"{API}/admin/businesses", headers=H(admin["tok"]))
        assert r.status_code == 200
        rows = r.json()
        assert all(row.get("billing") for row in rows), [row["name"] for row in rows if not row.get("billing")]
        for row in rows:
            for k in ("ai_cost_month", "ai_calls_month", "revenue"):
                assert k in row
        me = next(row for row in rows if row["id"] == shop_a["bid"])
        assert me["billing"]["plan"] == "trial" and me["revenue"] == 15.0
        assert me["ai_calls_month"] >= 1
        plat = next(row for row in rows if row["id"] == admin["bid"])
        assert plat["billing"]["exempt"] is True

    def test_owner_403(self, shop_a):
        assert requests.get(f"{API}/admin/businesses", headers=H(shop_a["tok"])).status_code == 403


# ---------- Paused state ----------
class TestPaused:
    def test_used_up_and_ended(self, shop_b):
        bid = shop_b["bid"]
        DB.subscriptions.update_one({"business_id": bid}, {"$set": {"used": 3000, "extra": 0}})
        s = requests.get(f"{API}/billing", headers=H(shop_b["tok"])).json()["sub"]
        assert s["paused"] is True and s["reason"] == "used_up"
        DB.subscriptions.update_one({"business_id": bid}, {"$set": {"used": 0, "paid_until": "2025-01-01T00:00:00+00:00"}})
        s = requests.get(f"{API}/billing", headers=H(shop_b["tok"])).json()["sub"]
        assert s["paused"] is True and s["reason"] == "ended" and s["pro"] is False
        assert requests.post(f"{API}/notion/sync", headers=H(shop_b["tok"])).status_code == 402
        time.sleep(0)
