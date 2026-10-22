# Iteration 16: live retest — latte regression (RF-8hex, $5.00 pending, mark-paid), English paid msg with ៛, prompt rule sampling (mixed/range carts)
import re
import sys
import time
import uuid

import pytest
import requests

sys.path.insert(0, "/app/backend/tests")
from test_iter15_khqr_live import API, BID, LT, H, chat, khqrs, mdb  # noqa: E402,F401

QR_CLAIM = re.compile(r"(sending|sent|send you|here is|here's|attached|scan (it|the|this)|below).{0,40}(QR|KHQR)|(QR|KHQR).{0,30}(sent|below|attached|here)", re.I | re.S)
RESULTS = []


def test_unique_index():
    idx = {i["name"]: i for i in mdb.orders.list_indexes()}
    assert idx["business_id_1_number_1"].get("unique") is True


class TestLatte:
    sid = "TEST_khqr16_" + uuid.uuid4().hex[:8]

    def test_latte_and_mark_paid(self, H):  # noqa: F811
        rep = chat(self.sid, "I want to buy 2 Iced Palm Sugar Latte")
        print("LATTE:", rep["text"])
        k = khqrs(rep)
        assert len(k) == 1, rep
        k = k[0]
        assert k["amount_text"] == "$5.00" and k["status"] == "pending"
        assert re.fullmatch(r"RF-[0-9A-F]{8}", k["number"]), k["number"]
        r = requests.post(f"{API}/orders/{k['order_id']}/mark-paid", headers=H, timeout=30)
        assert r.status_code == 200 and r.json()["status"] == "paid"
        h = requests.get(f"{API}/public/{BID}/chat/{self.sid}", timeout=30).json()
        msgs = h["messages"] if isinstance(h, dict) else h
        assert [m for m in msgs if m.get("text", "").startswith("Payment received") and k["number"] in m["text"]]


class TestPromptRule:
    @pytest.fixture(scope="class")
    def prods(self, H):  # noqa: F811
        out = {}
        for name, price in [("TEST Num Pang Sandwich", "15000៛"), ("TEST Mystery Box", "10-15$")]:
            r = requests.post(f"{API}/products", headers=H, json={"name": name, "price": price, "description": "test product"}, timeout=30)
            assert r.status_code in (200, 201), r.text
            out[name] = r.json()["id"]
        yield out
        for pid in out.values():
            requests.delete(f"{API}/products/{pid}", headers=H, timeout=30)
        print("PROMPT RULE RESULTS:", RESULTS)

    def test_english_riel_paid_msg(self, prods, H):  # noqa: F811
        sid = "TEST_khqr16_riel_" + uuid.uuid4().hex[:6]
        rep = chat(sid, "I want to buy 1 TEST Num Pang Sandwich for 15,000៛, confirmed, how do I pay?")
        print("RIEL:", rep["text"])
        k = khqrs(rep)
        assert len(k) == 1 and k[0]["amount_text"] == "15,000៛", rep
        r = requests.post(f"{API}/orders/{k[0]['order_id']}/mark-paid", headers=H, timeout=30)
        assert r.status_code == 200
        conv_id = mdb.orders.find_one({"id": k[0]["order_id"]})["conversation_id"]
        m = mdb.messages.find_one({"conversation_id": conv_id, "role": "ai"}, sort=[("created_at", -1)])
        print("RIEL paid:", m["text"])
        assert m["text"].startswith("Payment received"), m["text"]

    @pytest.mark.parametrize("i,msg", [
        (1, "I want to buy 1 Iced Palm Sugar Latte and 1 TEST Num Pang Sandwich, confirmed, how do I pay?"),
        (2, "Please send me the QR for 2 Iced Palm Sugar Latte and 2 TEST Num Pang Sandwich together, I confirm."),
        (3, "I want to buy 1 TEST Mystery Box, confirmed, how do I pay?"),
        (4, "Order 2 TEST Mystery Box for me please, I confirm, send the QR."),
    ])
    def test_rule(self, prods, i, msg):
        time.sleep(4)
        rep = chat("TEST_khqr16_rule%d_" % i + uuid.uuid4().hex[:6], msg)
        txt = rep["text"]
        claim = bool(QR_CLAIM.search(txt.split("(Sorry, the payment QR")[0]))
        fail = "payment QR could not be created" in txt
        RESULTS.append({"case": i, "khqr": bool(khqrs(rep)), "claims_qr": claim, "qr_fail_line": fail, "text": txt[:300]})
        print(f"RULE{i}: claim={claim} fail={fail} :: {txt}")
        assert not khqrs(rep)
        if fail:
            assert txt.rstrip().endswith("Our team will send you the payment details.)")  # English fallback
