# Iteration 4: multi-tenant SaaS - signup, tenant isolation, public per-business endpoints, webhooks, admin, big inbox paging
import os, uuid, json, hmac, hashlib, time
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv('/app/frontend/.env')
load_dotenv('/app/backend/.env')
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api"
mdb = MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]

ADMIN = ("admin@replyflow.com", "admin123")
LT100 = ("loadtest+706ab4fd@example.com", "loadtest123")
LT3000 = ("loadtest+82c7ca04@example.com", "loadtest123")
CREATED_BIDS = []


def fake_ip():
    return f"10.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


def register(name, ip=None):
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "secret123", "business_name": name},
                      headers={"X-Forwarded-For": ip or fake_ip()})
    assert r.status_code == 200, r.text
    d = r.json()
    CREATED_BIDS.append(d["user"]["business_id"])
    return d, email


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for bid in CREATED_BIDS:
        for c in (mdb.users, mdb.conversations, mdb.messages, mdb.settings):
            c.delete_many({"business_id": bid})
        mdb.businesses.delete_many({"id": bid})


@pytest.fixture(scope="module")
def two_biz():
    a, ea = register("TEST_Biz A")
    b, eb = register("TEST_Biz B")
    return {"a": a, "b": b, "ea": ea, "eb": eb}


# ---- Signup ----
class TestSignup:
    def test_register_creates_business(self, two_biz):
        a = two_biz["a"]
        assert a["user"]["role"] == "owner"
        assert a["user"]["business_name"] == "TEST_Biz A"
        me = requests.get(f"{API}/auth/me", headers=hdr(a["token"])).json()
        assert me["business_id"] == a["user"]["business_id"]
        assert me["business_name"] == "TEST_Biz A"
        assert "password_hash" not in me
        s = requests.get(f"{API}/settings", headers=hdr(a["token"])).json()
        assert s["business_name"] == "TEST_Biz A"
        u = mdb.users.find_one({"email": two_biz["ea"]})
        assert u["password_hash"].startswith("$2b$")

    def test_register_duplicate(self, two_biz):
        r = requests.post(f"{API}/auth/register", json={"email": two_biz["ea"].upper(), "password": "secret123", "business_name": "X"},
                          headers={"X-Forwarded-For": fake_ip()})
        assert r.status_code == 400 and "already exists" in r.json()["detail"]

    def test_register_validation(self):
        ip = fake_ip()
        assert requests.post(f"{API}/auth/register", json={"email": "bad", "password": "secret123", "business_name": "X"}, headers={"X-Forwarded-For": ip}).status_code == 400
        assert requests.post(f"{API}/auth/register", json={"email": "a@b.co", "password": "123", "business_name": "X"}, headers={"X-Forwarded-For": ip}).status_code == 422
        assert requests.post(f"{API}/auth/register", json={"email": "a@b.co", "password": "secret123", "business_name": ""}, headers={"X-Forwarded-For": ip}).status_code == 422

    def test_login_new_account(self, two_biz):
        d = login(two_biz["eb"], "secret123")
        assert d["user"]["business_id"] == two_biz["b"]["user"]["business_id"]


# ---- Tenant isolation ----
class TestIsolation:
    def test_isolation_full(self, two_biz):
        a, b = two_biz["a"], two_biz["b"]
        _bida, bidb = a["user"]["business_id"], b["user"]["business_id"]
        # turn off auto reply on both to avoid LLM
        for t in (a, b):
            s = requests.get(f"{API}/settings", headers=hdr(t["token"])).json()
            s["auto_reply"] = False
            assert requests.put(f"{API}/settings", json=s, headers=hdr(t["token"])).status_code == 200
        sess = f"TEST_sess_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/public/{bidb}/chat", json={"session_id": sess, "text": "hello from B customer"})
        assert r.status_code == 200 and r.json()["reply"] is None
        lb = requests.get(f"{API}/conversations", headers=hdr(b["token"])).json()
        assert lb["total"] == 1 and lb["items"][0]["external_id"] == sess
        cid = lb["items"][0]["id"]
        la = requests.get(f"{API}/conversations", headers=hdr(a["token"])).json()
        assert la["total"] == 0 and la["items"] == []
        H = hdr(a["token"])
        assert requests.get(f"{API}/conversations/{cid}/messages", headers=H).status_code == 404
        assert requests.post(f"{API}/conversations/{cid}/reply", json={"text": "hack"}, headers=H).status_code == 404
        assert requests.post(f"{API}/conversations/{cid}/suggest", headers=H).status_code == 404
        assert requests.post(f"{API}/conversations/{cid}/summary", headers=H).status_code == 404
        assert requests.patch(f"{API}/conversations/{cid}", json={"ai_enabled": False}, headers=H).status_code == 404
        # owner B can still access
        assert requests.get(f"{API}/conversations/{cid}/messages", headers=hdr(b["token"])).status_code == 200
        conv = mdb.conversations.find_one({"id": cid})
        assert conv["ai_enabled"] is True
        # stats isolated
        assert requests.get(f"{API}/stats", headers=H).json()["total"] == 0
        # admin (superadmin) also must not see B conv in own inbox
        adm = login(*ADMIN)
        assert requests.get(f"{API}/conversations/{cid}/messages", headers=hdr(adm["token"])).status_code == 404

    def test_settings_isolation(self, two_biz):
        a, b = two_biz["a"], two_biz["b"]
        s = requests.get(f"{API}/settings", headers=hdr(a["token"])).json()
        s["business_info"] = "TEST_A secret info"
        s["greeting"] = "TEST greeting A"
        assert requests.put(f"{API}/settings", json=s, headers=hdr(a["token"])).status_code == 200
        sb = requests.get(f"{API}/settings", headers=hdr(b["token"])).json()
        assert sb["business_info"] != "TEST_A secret info" and sb["business_name"] == "TEST_Biz B"
        info = requests.get(f"{API}/public/{a['user']['business_id']}/info").json()
        assert info == {"business_name": "TEST_Biz A", "greeting": "TEST greeting A"}


# ---- Public endpoints ----
class TestPublic:
    def test_default_and_unknown(self):
        r = requests.get(f"{API}/public/default/info")
        assert r.status_code == 200 and "business_name" in r.json()
        assert requests.get(f"{API}/public/{uuid.uuid4()}/info").status_code == 404
        assert requests.post(f"{API}/public/{uuid.uuid4()}/chat", json={"session_id": "x", "text": "hi"}).status_code == 404
        assert requests.get(f"{API}/public/{uuid.uuid4()}/chat/x").status_code == 404

    def test_history_scoped(self, two_biz):
        bida, bidb = two_biz["a"]["user"]["business_id"], two_biz["b"]["user"]["business_id"]
        sess = f"TEST_h_{uuid.uuid4().hex[:6]}"
        requests.post(f"{API}/public/{bida}/chat", json={"session_id": sess, "text": "only in A"})
        ha = requests.get(f"{API}/public/{bida}/chat/{sess}").json()["messages"]
        hb = requests.get(f"{API}/public/{bidb}/chat/{sess}").json()["messages"]
        assert len(ha) == 1 and ha[0]["text"] == "only in A" and "_id" not in ha[0]
        assert hb == []

    def test_llm_reply_for_business(self, two_biz):
        a = two_biz["a"]
        s = requests.get(f"{API}/settings", headers=hdr(a["token"])).json()
        s["auto_reply"] = True
        s["business_info"] = "TEST cafe. Cappuccino costs $4."
        requests.put(f"{API}/settings", json=s, headers=hdr(a["token"]))
        r = requests.post(f"{API}/public/{a['user']['business_id']}/chat", json={"session_id": f"TEST_llm_{uuid.uuid4().hex[:5]}", "text": "How much is a cappuccino?"}, timeout=90)
        assert r.status_code == 200
        rep = r.json()["reply"]
        assert rep and rep["role"] == "ai" and "4" in rep["text"]
        s["auto_reply"] = False
        requests.put(f"{API}/settings", json=s, headers=hdr(a["token"]))


# ---- Webhooks per business ----
class TestWebhooks:
    def test_telegram_requires_secret(self, two_biz):
        a = two_biz["a"]
        bid = a["user"]["business_id"]
        assert requests.post(f"{API}/webhooks/telegram/{bid}", json={"message": {"text": "x", "chat": {"id": 1}}}).status_code == 403
        s = requests.get(f"{API}/settings", headers=hdr(a["token"])).json()
        s["telegram_token"] = "123:TESTFAKE"
        requests.put(f"{API}/settings", json=s, headers=hdr(a["token"]))
        assert requests.post(f"{API}/webhooks/telegram/{bid}", json={"message": {"text": "x", "chat": {"id": 1}}}).status_code == 403
        assert requests.post(f"{API}/webhooks/telegram/{bid}", json={}, headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"}).status_code == 403
        assert requests.post(f"{API}/webhooks/telegram/{uuid.uuid4()}", json={}).status_code == 403
        s["telegram_token"] = ""
        requests.put(f"{API}/settings", json=s, headers=hdr(a["token"]))

    def test_messenger_verify_and_signature(self, two_biz):
        a, b = two_biz["a"], two_biz["b"]
        bida, bidb = a["user"]["business_id"], b["user"]["business_id"]
        s = requests.get(f"{API}/settings", headers=hdr(a["token"])).json()
        s.update({"fb_verify_token": "TEST_verify_A", "fb_app_secret": "TEST_secret_A", "auto_reply": False})
        requests.put(f"{API}/settings", json=s, headers=hdr(a["token"]))
        q = {"hub.mode": "subscribe", "hub.verify_token": "TEST_verify_A", "hub.challenge": "abc123"}
        r = requests.get(f"{API}/webhooks/messenger/{bida}", params=q)
        assert r.status_code == 200 and r.text == "abc123"
        assert requests.get(f"{API}/webhooks/messenger/{bidb}", params=q).status_code == 403
        payload = json.dumps({"entry": [{"messaging": [{"sender": {"id": "TESTPSID9876"}, "message": {"text": "hi via fb"}}]}]}).encode()
        sig = "sha256=" + hmac.new(b"TEST_secret_A", payload, hashlib.sha256).hexdigest()
        assert requests.post(f"{API}/webhooks/messenger/{bida}", data=payload, headers={"X-Hub-Signature-256": "sha256=bad", "Content-Type": "application/json"}).status_code == 403
        assert requests.post(f"{API}/webhooks/messenger/{bidb}", data=payload, headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"}).status_code == 403
        r = requests.post(f"{API}/webhooks/messenger/{bida}", data=payload, headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"})
        assert r.status_code == 200
        time.sleep(2)
        la = requests.get(f"{API}/conversations", params={"channel": "messenger"}, headers=hdr(a["token"])).json()
        assert la["total"] == 1 and la["items"][0]["external_id"] == "TESTPSID9876"
        lb = requests.get(f"{API}/conversations", params={"channel": "messenger"}, headers=hdr(b["token"])).json()
        assert lb["total"] == 0


# ---- Platform admin ----
class TestAdmin:
    def test_superadmin_lists(self, two_biz):
        adm = login(*ADMIN)
        assert adm["user"]["role"] == "superadmin"
        rows = requests.get(f"{API}/admin/businesses", headers=hdr(adm["token"])).json()
        by = {r["id"]: r for r in rows}
        counts = sorted(r["conversations"] for r in rows if (r["owner_email"] or "").startswith("loadtest"))
        assert counts == [100, 3000]
        assert two_biz["a"]["user"]["business_id"] in by
        assert by[two_biz["a"]["user"]["business_id"]]["owner_email"] == two_biz["ea"]

    def test_owner_forbidden(self, two_biz):
        for creds in (LT100, LT3000):
            t = login(*creds)["token"]
            assert requests.get(f"{API}/admin/businesses", headers=hdr(t)).status_code == 403
        assert requests.get(f"{API}/admin/businesses", headers=hdr(two_biz["a"]["token"])).status_code == 403
        assert requests.get(f"{API}/admin/businesses").status_code == 401


# ---- Big inbox paging ----
class TestBigInbox:
    def test_paging_3000_no_dupes(self):
        t = login(*LT3000)["token"]
        seen, before, pages = [], None, 0
        while True:
            p = {"limit": 100}
            if before:
                p["before"] = before
            d = requests.get(f"{API}/conversations", params=p, headers=hdr(t)).json()
            assert d["total"] == 3000
            seen += [c["id"] for c in d["items"]]
            pages += 1
            if not d["has_more"]:
                break
            before = d["items"][-1]["updated_at"]
            assert pages < 50
        assert len(seen) == 3000 and len(set(seen)) == 3000

    def test_filter_and_search(self):
        t = login(*LT3000)["token"]
        d = requests.get(f"{API}/conversations", params={"channel": "telegram"}, headers=hdr(t)).json()
        assert d["total"] == 1000 and all(c["channel"] == "telegram" for c in d["items"])
        d = requests.get(f"{API}/conversations", params={"q": "cappuccino"}, headers=hdr(t)).json()
        assert d["total"] > 0
        cid = d["items"][-1]["id"]
        m = requests.get(f"{API}/conversations/{cid}/messages", headers=hdr(t))
        assert m.status_code == 200 and len(m.json()) > 0

    def test_limit_validation(self):
        t = login(*LT3000)["token"]
        assert requests.get(f"{API}/conversations", params={"limit": 500}, headers=hdr(t)).status_code == 422

    def test_lt100_all_ai(self):
        t = login(*LT100)["token"]
        st = requests.get(f"{API}/stats", headers=hdr(t)).json()
        assert st["total"] == 100 and st["ai_replies"] >= 100
