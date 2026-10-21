# ReplyFlow iteration 2: messenger signature, public chat rate limit, widget.js, quick replies, AI summary
import os
import time
import json
import hmac
import hashlib
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@replyflow.com", "password": "admin123"}
SECRET = "TEST_app_secret_123"


@pytest.fixture(scope="session")
def s():
    return requests.Session()


@pytest.fixture(scope="session")
def H(s):
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
    if r.status_code != 200:
        pytest.skip("login failed")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="session", autouse=True)
def restore(s, H):
    orig = s.get(f"{BASE_URL}/api/settings", headers=H).json()
    yield
    orig.update({"fb_app_secret": "", "fb_page_token": "", "fb_verify_token": ""})
    s.put(f"{BASE_URL}/api/settings", json=orig, headers=H)


def sign(body: bytes, secret=SECRET):
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def fb_payload(psid, text):
    return json.dumps({"object": "page", "entry": [{"id": "1", "messaging": [
        {"sender": {"id": psid}, "recipient": {"id": "1"}, "message": {"mid": "m1", "text": text}}]}]}).encode()


# --- Messenger signature
class TestMessengerSignature:
    def test_403_when_secret_not_set(self, s, H):
        st = s.get(f"{BASE_URL}/api/settings", headers=H).json()
        st["fb_app_secret"] = ""
        s.put(f"{BASE_URL}/api/settings", json=st, headers=H)
        body = fb_payload("TEST9990001", "hi")
        r = s.post(f"{BASE_URL}/api/webhooks/messenger", data=body,
                   headers={"Content-Type": "application/json", "X-Hub-Signature-256": sign(body, "")})
        assert r.status_code == 403

    def test_403_missing_and_invalid(self, s, H):
        st = s.get(f"{BASE_URL}/api/settings", headers=H).json()
        st["fb_app_secret"] = SECRET
        assert s.put(f"{BASE_URL}/api/settings", json=st, headers=H).status_code == 200
        body = fb_payload("TEST9990002", "hi")
        r1 = s.post(f"{BASE_URL}/api/webhooks/messenger", data=body, headers={"Content-Type": "application/json"})
        r2 = s.post(f"{BASE_URL}/api/webhooks/messenger", data=body,
                    headers={"Content-Type": "application/json", "X-Hub-Signature-256": sign(body, "wrong")})
        r3 = s.post(f"{BASE_URL}/api/webhooks/messenger", data=body,
                    headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=deadbeef"})
        assert (r1.status_code, r2.status_code, r3.status_code) == (403, 403, 403)

    def test_valid_signature_creates_conv_and_ai_reply(self, s, H):
        psid = f"TEST{uuid.uuid4().int % 10**10}"
        body = fb_payload(psid, "Hello, what are your opening hours?")
        r = s.post(f"{BASE_URL}/api/webhooks/messenger", data=body,
                   headers={"Content-Type": "application/json", "X-Hub-Signature-256": sign(body)})
        assert r.status_code == 200 and r.json() == {"ok": True}
        conv = None
        for _ in range(15):
            time.sleep(2)
            convs = s.get(f"{BASE_URL}/api/conversations", params={"channel": "messenger"}, headers=H).json()
            conv = next((c for c in convs if c["external_id"] == psid), None)
            if conv:
                msgs = s.get(f"{BASE_URL}/api/conversations/{conv['id']}/messages", headers=H).json()
                if any(m["role"] == "ai" for m in msgs):
                    break
        assert conv is not None
        assert conv["name"] == f"Messenger user {psid[-4:]}"
        roles = [m["role"] for m in msgs]
        assert "user" in roles and "ai" in roles


# --- Channel status
class TestChannelStatus:
    def test_messenger_configured_requires_all_three(self, s, H):
        st = s.get(f"{BASE_URL}/api/settings", headers=H).json()
        st.update({"fb_page_token": "TEST_page", "fb_verify_token": "TEST_verify", "fb_app_secret": ""})
        s.put(f"{BASE_URL}/api/settings", json=st, headers=H)
        assert s.get(f"{BASE_URL}/api/channels/status", headers=H).json()["messenger"]["configured"] is False
        st["fb_app_secret"] = SECRET
        s.put(f"{BASE_URL}/api/settings", json=st, headers=H)
        assert s.get(f"{BASE_URL}/api/channels/status", headers=H).json()["messenger"]["configured"] is True
        assert s.get(f"{BASE_URL}/api/settings", headers=H).json()["fb_app_secret"] == SECRET


# --- Widget
class TestWidget:
    def test_widget_js(self, s):
        r = s.get(f"{BASE_URL}/api/widget.js")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/javascript")
        assert "replyflow-bubble" in r.text and "/embed?b=" in r.text and "data-color" in r.text


# --- Quick replies
class TestQuickReplies:
    def test_defaults_and_persist(self, s, H):
        st = s.get(f"{BASE_URL}/api/settings", headers=H).json()
        labels = [q["label"] for q in st["quick_replies"]]
        assert len(labels) >= 1
        orig = st["quick_replies"]
        st["quick_replies"] = orig + [{"label": "TEST_label", "text": "TEST_text"}]
        s.put(f"{BASE_URL}/api/settings", json=st, headers=H)
        got = s.get(f"{BASE_URL}/api/settings", headers=H).json()["quick_replies"]
        assert got[-1] == {"label": "TEST_label", "text": "TEST_text"}
        st["quick_replies"] = orig
        s.put(f"{BASE_URL}/api/settings", json=st, headers=H)


# --- Public chat validation + rate limit (keep last: consumes IP budget)
class TestPublicChatLimits:
    def test_text_too_long_422(self, s):
        r = s.post(f"{BASE_URL}/api/public/default/chat", json={"session_id": f"TEST_long_{uuid.uuid4().hex[:6]}", "text": "a" * 2001})
        assert r.status_code == 422

    def test_session_rate_limit_429(self, s, H):
        sid = f"TEST_rl_{uuid.uuid4().hex[:8]}"
        # disable AI auto reply so the 7 requests fit well within the 60s window
        st = s.get(f"{BASE_URL}/api/settings", headers=H).json()
        st["auto_reply"] = False
        s.put(f"{BASE_URL}/api/settings", json=st, headers=H)
        codes = []
        for i in range(7):
            r = s.post(f"{BASE_URL}/api/public/default/chat", json={"session_id": sid, "text": f"ping {i}"}, timeout=60)
            codes.append(r.status_code)
            if r.status_code == 429:
                detail = r.json().get("detail")
        st["auto_reply"] = True
        s.put(f"{BASE_URL}/api/settings", json=st, headers=H)
        assert codes[:6] == [200] * 6, codes
        assert codes[6] == 429
        assert "too fast" in detail


# --- Summary caching (uses an existing conv with user msgs)
class TestSummary:
    def test_summary_cache_and_force(self, s, H):
        convs = s.get(f"{BASE_URL}/api/conversations", params={"channel": "messenger"}, headers=H).json()
        conv = next(c for c in convs if c["external_id"].startswith("TEST"))
        r1 = s.post(f"{BASE_URL}/api/conversations/{conv['id']}/summary", headers=H, timeout=90)
        assert r1.status_code == 200
        d1 = r1.json()
        for k in ["intent", "summary", "stage", "details", "next_step", "updated_at"]:
            assert k in d1
        assert isinstance(d1["details"], list)
        r2 = s.post(f"{BASE_URL}/api/conversations/{conv['id']}/summary", headers=H, timeout=90).json()
        assert r2["updated_at"] == d1["updated_at"]
        r3 = s.post(f"{BASE_URL}/api/conversations/{conv['id']}/summary", params={"force": "true"}, headers=H, timeout=90).json()
        assert r3["updated_at"] != d1["updated_at"]
        # message count change -> regenerated
        s.post(f"{BASE_URL}/api/conversations/{conv['id']}/reply", json={"text": "TEST agent msg"}, headers=H)
        r4 = s.post(f"{BASE_URL}/api/conversations/{conv['id']}/summary", headers=H, timeout=90).json()
        assert r4["updated_at"] != r3["updated_at"]
        listed = s.get(f"{BASE_URL}/api/conversations", headers=H).json()
        assert next(c for c in listed if c["id"] == conv["id"])["summary"]["intent"] == r4["intent"]

    def test_summary_404(self, s, H):
        r = s.post(f"{BASE_URL}/api/conversations/nonexistent-xyz/summary", headers=H)
        assert r.status_code == 404

    def test_summary_requires_auth(self, s):
        r = s.post(f"{BASE_URL}/api/conversations/x/summary")
        assert r.status_code == 401
