# ReplyFlow API regression tests: auth, settings, public chat, inbox, AI, webhooks, channels
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@replyflow.com", "password": "admin123"}


@pytest.fixture(scope="session")
def s():
    return requests.Session()


@pytest.fixture(scope="session")
def token(s):
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
    if r.status_code != 200:
        pytest.skip(f"login failed {r.status_code}")
    return r.json()["token"]


@pytest.fixture(scope="session")
def H(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session", autouse=True)
def restore_settings(s, H):
    orig = s.get(f"{BASE_URL}/api/settings", headers=H).json()
    yield
    s.put(f"{BASE_URL}/api/settings", json=orig, headers=H)


# --- Auth
class TestAuth:
    def test_login_ok(self, s):
        r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["email"] == ADMIN["email"] and d["token"]

    def test_login_bad(self, s):
        r = s.post(f"{BASE_URL}/api/auth/login", json={"email": f"TEST_{uuid.uuid4().hex[:6]}@x.com", "password": "nope"})
        assert r.status_code == 401

    def test_me(self, s, H):
        r = s.get(f"{BASE_URL}/api/auth/me", headers=H)
        assert r.status_code == 200 and r.json()["email"] == ADMIN["email"]
        assert "password_hash" not in r.json()

    def test_unauth(self, s):
        assert s.get(f"{BASE_URL}/api/conversations").status_code == 401
        assert s.get(f"{BASE_URL}/api/settings", headers={"Authorization": "Bearer bad"}).status_code == 401

    def test_bruteforce_lockout(self, s):
        email = f"TEST_lock_{uuid.uuid4().hex[:6]}@x.com"
        codes = [s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "x"}).status_code for _ in range(6)]
        assert codes[:5] == [401] * 5 and codes[5] == 429


# --- Settings
class TestSettings:
    def test_settings_roundtrip(self, s, H):
        cur = s.get(f"{BASE_URL}/api/settings", headers=H).json()
        cur.update({"business_name": "TEST_Shop", "faqs": [{"q": "Do you ship to Mars?", "a": "Yes, Mars shipping costs $999 and takes 7 months."}], "model": "gemini"})
        r = s.put(f"{BASE_URL}/api/settings", json=cur, headers=H)
        assert r.status_code == 200
        g = s.get(f"{BASE_URL}/api/settings", headers=H).json()
        assert g["business_name"] == "TEST_Shop" and g["model"] == "gemini" and g["faqs"][0]["q"].startswith("Do you ship")
        assert s.get(f"{BASE_URL}/api/public/default/info").json()["business_name"] == "TEST_Shop"

    def test_ai_test_uses_faq_gemini(self, s, H):
        r = s.post(f"{BASE_URL}/api/ai/test", json={"text": "Do you ship to Mars? how much?"}, headers=H, timeout=60)
        assert r.status_code == 200, r.text
        assert "999" in r.json()["reply"]

    def test_ai_test_claude(self, s, H):
        cur = s.get(f"{BASE_URL}/api/settings", headers=H).json()
        cur["model"] = "claude"
        s.put(f"{BASE_URL}/api/settings", json=cur, headers=H)
        r = s.post(f"{BASE_URL}/api/ai/test", json={"text": "Do you ship to Mars?"}, headers=H, timeout=60)
        assert r.status_code == 200 and len(r.json()["reply"]) > 0


# --- Public chat + inbox
class TestChatInbox:
    sid = f"web-TEST_{uuid.uuid4().hex[:8]}"
    cid = None

    def test_public_chat_ai_reply(self, s):
        r = s.post(f"{BASE_URL}/api/public/default/chat", json={"session_id": self.sid, "text": "Hi, what are your hours?"}, timeout=60)
        assert r.status_code == 200
        rep = r.json()["reply"]
        assert rep and rep["role"] == "ai" and rep["text"]
        h = s.get(f"{BASE_URL}/api/public/default/chat/{self.sid}").json()["messages"]
        assert [m["role"] for m in h] == ["user", "ai"]

    def test_empty_message(self, s):
        assert s.post(f"{BASE_URL}/api/public/default/chat", json={"session_id": self.sid, "text": "  "}).status_code == 400

    def test_inbox_lists_and_filters(self, s, H):
        convs = s.get(f"{BASE_URL}/api/conversations", params={"channel": "web"}, headers=H).json()["items"]
        c = next(c for c in convs if c["external_id"] == self.sid)
        TestChatInbox.cid = c["id"]
        assert c["channel"] == "web" and c["ai_enabled"] is True
        tg = s.get(f"{BASE_URL}/api/conversations", params={"channel": "telegram"}, headers=H).json()["items"]
        assert all(x["channel"] == "telegram" for x in tg)
        q = s.get(f"{BASE_URL}/api/conversations", params={"q": "what are your hours"}, headers=H).json()["items"]
        assert isinstance(q, list)

    def test_suggest(self, s, H):
        r = s.post(f"{BASE_URL}/api/conversations/{self.cid}/suggest", headers=H, timeout=60)
        assert r.status_code == 200
        assert len(r.json()["suggestions"]) == 3

    def test_manual_reply_visible_publicly(self, s, H):
        r = s.post(f"{BASE_URL}/api/conversations/{self.cid}/reply", json={"text": "TEST_agent hello"}, headers=H)
        assert r.status_code == 200 and r.json()["role"] == "agent"
        h = s.get(f"{BASE_URL}/api/public/default/chat/{self.sid}").json()["messages"]
        assert h[-1]["text"] == "TEST_agent hello"

    def test_ai_toggle(self, s, H):
        r = s.patch(f"{BASE_URL}/api/conversations/{self.cid}", json={"ai_enabled": False}, headers=H)
        assert r.status_code == 200 and r.json()["ai_enabled"] is False
        r = s.post(f"{BASE_URL}/api/public/default/chat", json={"session_id": self.sid, "text": "are you there?"}, timeout=60)
        assert r.json()["reply"] is None
        s.patch(f"{BASE_URL}/api/conversations/{self.cid}", json={"ai_enabled": True}, headers=H)
        r = s.post(f"{BASE_URL}/api/public/default/chat", json={"session_id": self.sid, "text": "hello again"}, timeout=60)
        assert r.json()["reply"]["role"] == "ai"

    def test_404s(self, s, H):
        assert s.patch(f"{BASE_URL}/api/conversations/nope", json={"unread": 0}, headers=H).status_code == 404
        assert s.post(f"{BASE_URL}/api/conversations/nope/reply", json={"text": "x"}, headers=H).status_code == 404

    def test_stats(self, s, H):
        d = s.get(f"{BASE_URL}/api/stats", headers=H).json()
        assert d["web"] >= 1 and d["ai_replies"] >= 1


# --- Webhooks & channels
class TestWebhooks:
    def test_messenger_verify(self, s, H):
        cur = s.get(f"{BASE_URL}/api/settings", headers=H).json()
        cur["fb_verify_token"] = "TEST_verify"
        s.put(f"{BASE_URL}/api/settings", json=cur, headers=H)
        r = s.get(f"{BASE_URL}/api/webhooks/messenger", params={"hub.mode": "subscribe", "hub.verify_token": "TEST_verify", "hub.challenge": "123"})
        assert r.status_code == 200 and r.text == "123"
        r = s.get(f"{BASE_URL}/api/webhooks/messenger", params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "123"})
        assert r.status_code == 403

    def test_messenger_ingest(self, s, H):
        psid = f"TEST{uuid.uuid4().hex[:10]}"
        payload = {"object": "page", "entry": [{"id": "1", "time": 1, "messaging": [
            {"sender": {"id": psid}, "recipient": {"id": "1"}, "timestamp": 1, "message": {"mid": "m1", "text": "Hello from messenger, do you ship to Mars?"}}]}]}
        # Since iteration 2, unsigned payloads must be rejected (signed flow: test_iter2_security_widget_summary.py)
        r = s.post(f"{BASE_URL}/api/webhooks/messenger", json=payload)
        assert r.status_code == 403

    def test_telegram_bad_secret(self, s):
        r = s.post(f"{BASE_URL}/api/webhooks/telegram/123", json={"message": {"text": "hi", "chat": {"id": 1}}})
        assert r.status_code == 403

    def test_telegram_connect_fake_token(self, s, H):
        cur = s.get(f"{BASE_URL}/api/settings", headers=H).json()
        cur["telegram_token"] = "123456:FAKE_TOKEN"
        s.put(f"{BASE_URL}/api/settings", json=cur, headers=H)
        r = s.post(f"{BASE_URL}/api/channels/telegram/connect", json={"base_url": BASE_URL}, headers=H, timeout=30)
        assert r.status_code == 400 and "Telegram rejected" in r.json()["detail"]
        st = s.get(f"{BASE_URL}/api/channels/status", headers=H, timeout=30)
        assert st.status_code == 200 and st.json()["telegram"]["connected"] is False
