# Iteration 15: Bakong KHQR payments — live API tests (settings validation, preview, AI order flow, mark-paid/cancel, expiry, cross-tenant)
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np
import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
from payments import _crc16, _tlv  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
API = BASE_URL + "/api"
BID = "4f0dbc25-7fad-40f4-b898-0ef8db1d9799"
LT = ("loadtest+706ab4fd@example.com", "loadtest123")
ADMIN = ("admin@replyflow.com", "admin123")
env = dict(l.split("=", 1) for l in open("/app/backend/.env").read().splitlines() if "=" in l)
mdb = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
STATE = {}


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


def chat(sid, text, retries=3):
    for _ in range(retries):
        r = requests.post(f"{API}/public/{BID}/chat", json={"session_id": sid, "text": text, "name": "TEST_khqr"}, timeout=120)
        if r.status_code == 429:
            time.sleep(20)
            continue
        assert r.status_code == 200, r.text
        return r.json()["reply"]
    pytest.fail("rate limited")


def khqrs(reply):
    return [a for a in (reply or {}).get("attachments", []) if a.get("type") == "khqr"]


def decode(media_id):
    r = requests.get(f"{API}/media/{media_id}", timeout=30)
    assert r.status_code == 200 and r.content[:8] == b"\x89PNG\r\n\x1a\n", r.status_code
    img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    data, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    assert data, "QR not decodable"
    return data


def check_emv(qr, amount, cur, number, account="sambath@aclb"):
    assert qr.endswith(_crc16(qr[:-4])), "CRC mismatch"
    t = dict(_tlv(qr[:-8]))
    assert float(t["54"]) == amount, t["54"]
    assert t["53"] == cur
    assert account in t["29"]
    assert t["59"]
    assert number in t["62"]
    sub = dict(_tlv(t["99"]))
    assert int(sub["01"]) - int(sub["00"]) == 600000
    return t


def settings(H):
    return requests.get(f"{API}/settings", headers=H, timeout=30).json()


def put(H, **kw):
    s = settings(H)
    s.update(kw)
    return requests.put(f"{API}/settings", headers=H, json=s, timeout=30)


# ---- Settings validation & preview
class TestSettings:
    def test_bad_account(self, H):
        r = put(H, bakong_account_id="not an id")
        assert r.status_code == 400 and "Bakong account ID looks wrong" in r.text

    def test_bad_token(self, H):
        r = put(H, khqr_token="abc123")
        assert r.status_code == 400 and "rbk" in r.text

    def test_preview_ok(self, H):
        assert settings(H)["bakong_account_id"] == "sambath@aclb"
        r = requests.post(f"{API}/payments/preview", headers=H, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["mode"] == "local"
        qr = decode(d["media_id"])
        check_emv(qr, 1.0, "840", "RF-TEST")

    def test_preview_fake_token(self, H):
        r = put(H, khqr_token="rbk_fake_token_123")
        assert r.status_code == 200
        try:
            r = requests.post(f"{API}/payments/preview", headers=H, timeout=60)
            assert r.status_code == 400 and "KHQR.dev token problem" in r.text, r.text
            print("fake token preview:", r.text)
        finally:
            assert put(H, khqr_token="").status_code == 200
        assert settings(H)["khqr_token"] == ""

    def test_preview_no_account(self, AH):
        # admin business: verify only if it has no account (we don't modify admin settings)
        s = settings(AH)
        if s.get("bakong_account_id") or s.get("khqr_token"):
            pytest.skip("admin has payments configured")
        r = requests.post(f"{API}/payments/preview", headers=AH, timeout=30)
        assert r.status_code == 400


# ---- AI order flow (web widget)
class TestOrderFlow:
    sid = "TEST_khqr_" + uuid.uuid4().hex[:8]

    def test_a_vague(self):
        rep = chat(self.sid, "how much is the latte?")
        print("A:", rep["text"])
        assert not khqrs(rep)

    def test_b_confirmed(self):
        t0 = datetime.now(timezone.utc)
        rep = chat(self.sid, "I want to buy 2 Iced Palm Sugar Latte, how do I pay?")
        print("B:", rep["text"])
        k = khqrs(rep)
        assert len(k) == 1, rep
        k = k[0]
        assert k["amount_text"] == "$5.00" and k["status"] == "pending" and k["number"].startswith("RF-")
        assert "5.00" in rep["text"] or "$5" in rep["text"]
        exp = datetime.fromisoformat(k["expires_at"])
        assert timedelta(minutes=9) < exp - t0 < timedelta(minutes=11)
        check_emv(decode(k["media_id"]), 5.0, "840", k["number"])
        STATE["o1"], STATE["msg1"] = k, rep["id"]

    def test_d_change(self):
        time.sleep(3)
        rep = chat(self.sid, "make it 3 instead")
        print("D:", rep["text"])
        k = khqrs(rep)
        assert len(k) == 1 and k[0]["amount_text"] == "$7.50", rep
        o1 = mdb.orders.find_one({"id": STATE["o1"]["order_id"]})
        assert o1["status"] == "cancelled"
        m = mdb.messages.find_one({"id": STATE["msg1"]})
        assert [a for a in m["attachments"] if a["type"] == "khqr"][0]["status"] == "cancelled"
        STATE["o2"] = k[0]

    def test_mark_paid(self, H):
        oid = STATE["o2"]["order_id"]
        r = requests.post(f"{API}/orders/{oid}/mark-paid", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "paid" and r.json()["paid_by"] == f"seller:{LT[0]}"
        r2 = requests.post(f"{API}/orders/{oid}/mark-paid", headers=H, timeout=30)
        assert r2.status_code == 409
        r3 = requests.post(f"{API}/orders/{oid}/cancel", headers=H, timeout=30)
        assert r3.status_code == 409
        h = requests.get(f"{API}/public/{BID}/chat/{self.sid}", timeout=30).json()
        msgs = h["messages"] if isinstance(h, dict) else h
        paid = [m for m in msgs if "Payment received" in m.get("text", "")]
        assert len(paid) == 1 and STATE["o2"]["number"] in paid[0]["text"] and "$7.50" in paid[0]["text"]
        k = [a for m in msgs for a in m.get("attachments", []) if a.get("order_id") == oid]
        assert k and k[0]["status"] == "paid"

    def test_cross_tenant(self, AH):
        oid = STATE["o2"]["order_id"]
        assert requests.post(f"{API}/orders/{oid}/mark-paid", headers=AH, timeout=30).status_code == 404
        assert requests.post(f"{API}/orders/{oid}/cancel", headers=AH, timeout=30).status_code == 404
        lst = requests.get(f"{API}/orders", headers=AH, timeout=30).json()
        assert all(o["id"] != oid for o in lst)
        assert all(o["business_id"] != BID for o in lst)

    def test_list_and_filter(self, H):
        lst = requests.get(f"{API}/orders", headers=H, timeout=30).json()
        assert any(o["id"] == STATE["o2"]["order_id"] for o in lst)
        assert all("qr" not in o and "md5" not in o and "_id" not in o for o in lst)
        paid = requests.get(f"{API}/orders?status=paid", headers=H, timeout=30).json()
        assert all(o["status"] == "paid" for o in paid)
        assert requests.get(f"{API}/orders?status=bogus", headers=H, timeout=30).status_code == 422


class TestKhmerAndExpiry:
    sid = "TEST_khqr_km_" + uuid.uuid4().hex[:8]

    def test_e_khmer(self, H):
        chat(self.sid, "តើ Iced Palm Sugar Latte តម្លៃប៉ុន្មាន?")
        time.sleep(3)
        rep = chat(self.sid, "ខ្ញុំចង់ទិញ ២ កែវ")
        print("E:", rep["text"])
        k = khqrs(rep)
        assert len(k) == 1 and k[0]["amount_text"] == "$5.00", rep
        STATE["km"] = k[0]

    def test_cancel_then_expiry(self, H):
        oid = STATE["km"]["order_id"]
        # expiry: push expires_at to the past
        mdb.orders.update_one({"id": oid}, {"$set": {"expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}})
        for _ in range(15):
            time.sleep(1)
            if mdb.orders.find_one({"id": oid})["status"] == "expired":
                break
        assert mdb.orders.find_one({"id": oid})["status"] == "expired"
        m = mdb.messages.find_one({"attachments.order_id": oid})
        assert [a for a in m["attachments"] if a.get("order_id") == oid][0]["status"] == "expired"

    def test_khmer_paid_msg(self, H):
        oid = STATE["km"]["order_id"]
        r = requests.post(f"{API}/orders/{oid}/mark-paid", headers=H, timeout=30)
        assert r.status_code == 200
        m = mdb.messages.find_one({"conversation_id": mdb.orders.find_one({"id": oid})["conversation_id"], "role": "ai"}, sort=[("created_at", -1)])
        print("KM paid:", m["text"])
        assert "បានទទួលការទូទាត់" in m["text"]

    def test_cancel_pending(self, H):
        sid = "TEST_khqr_c_" + uuid.uuid4().hex[:8]
        rep = chat(sid, "I'd like to order 1 Iced Palm Sugar Latte please, I confirm, send the QR")
        k = khqrs(rep)
        assert k, rep["text"]
        r = requests.post(f"{API}/orders/{k[0]['order_id']}/cancel", headers=H, timeout=30)
        assert r.status_code == 200 and r.json()["status"] == "cancelled"
        m = mdb.messages.find_one({"id": rep["id"]})
        assert [a for a in m["attachments"] if a["type"] == "khqr"][0]["status"] == "cancelled"


class TestPrices:
    @pytest.fixture(scope="class")
    def prods(self, H):
        out = {}
        for name, price in [("TEST Num Pang Sandwich", "15000៛"), ("TEST Mystery Box", "10-15$")]:
            r = requests.post(f"{API}/products", headers=H, json={"name": name, "price": price, "description": "test product"}, timeout=30)
            assert r.status_code in (200, 201), r.text
            out[name] = r.json()["id"]
        yield out
        for pid in out.values():
            requests.delete(f"{API}/products/{pid}", headers=H, timeout=30)

    def test_f_khr(self, prods):
        rep = chat("TEST_khqr_f_" + uuid.uuid4().hex[:6], "I want to buy 1 TEST Num Pang Sandwich, confirmed, how do I pay?")
        print("F:", rep["text"])
        k = khqrs(rep)
        assert len(k) == 1 and k[0]["amount_text"] == "15,000៛", rep
        check_emv(decode(k[0]["media_id"]), 15000, "116", k[0]["number"])

    def test_g_range(self, prods):
        time.sleep(5)
        rep = chat("TEST_khqr_g_" + uuid.uuid4().hex[:6], "I want to buy 1 TEST Mystery Box, confirmed, how do I pay?")
        print("G:", rep["text"])
        assert not khqrs(rep)
        assert rep["text"].rstrip().endswith("payment QR could not be created right now. Our team will send you the payment details.)")

    def test_g_mixed(self, prods):
        time.sleep(5)
        rep = chat("TEST_khqr_g2_" + uuid.uuid4().hex[:6], "I want to buy 1 Iced Palm Sugar Latte and 1 TEST Num Pang Sandwich, confirmed, how do I pay?")
        print("G2:", rep["text"])
        assert not khqrs(rep)
        assert "payment QR could not be created" in rep["text"]


class TestPaymentsOff:
    def test_h_off(self, H):
        assert put(H, bakong_account_id="").status_code == 200
        try:
            rep = chat("TEST_khqr_h_" + uuid.uuid4().hex[:6], "I want to buy 2 Iced Palm Sugar Latte, confirmed, how do I pay?")
            print("H:", rep["text"])
            assert not khqrs(rep)
            assert "payment QR could not be created" not in rep["text"]
            r = requests.post(f"{API}/payments/preview", headers=H, timeout=30)
            assert r.status_code == 400
        finally:
            assert put(H, bakong_account_id="sambath@aclb").status_code == 200
        assert settings(H)["bakong_account_id"] == "sambath@aclb"

    def test_ai_test_box(self, H):
        r = requests.post(f"{API}/ai/test", headers=H, json={"text": "I want to buy 2 Iced Palm Sugar Latte, confirmed"}, timeout=120)
        assert r.status_code == 200
        n = mdb.orders.count_documents({"business_id": BID})
        print("ai test:", r.json())
        assert r.json()["order_total"] == "$5.00"
        assert mdb.orders.count_documents({"business_id": BID}) == n
