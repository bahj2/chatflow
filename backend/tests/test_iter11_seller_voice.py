# Iteration 11: seller voice clone upload/delete, voice/test engines, multi-tenant media isolation, async widget voice
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
KM = "សួស្តីបង! អរគុណដែលបានទាក់ទងមកហាងយើងខ្ញុំ។"
TIMINGS = {}


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed {email}")
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin():
    return login("admin@replyflow.com", "admin123")


@pytest.fixture(scope="module")
def other():
    return login("loadtest+706ab4fd@example.com", "loadtest123")


def H(t):
    return {"Authorization": f"Bearer {t}"}


def up(token, path, name="s.mp3", ctype="audio/mpeg", text=""):
    with open(path, "rb") as f:
        return requests.post(f"{API}/settings/seller-voice", headers=H(token), files={"file": (name, f, ctype)}, data={"text": text}, timeout=120)


# --- validation
class TestSellerVoiceValidation:
    def test_too_short(self, admin):
        r = up(admin, "/tmp/short.mp3")
        assert r.status_code == 400
        assert "The sample is 3 seconds" in r.json()["detail"]

    def test_too_long(self, admin):
        r = up(admin, "/tmp/long40.mp3")
        assert r.status_code == 400
        assert "5–30 seconds" in r.json()["detail"]

    def test_tone_35(self, admin):
        r = up(admin, "/tmp/tone35.wav", "t.wav", "audio/wav")
        assert r.status_code == 400

    def test_non_audio(self, admin):
        r = up(admin, "/tmp/notaudio.txt", "a.txt", "text/plain")
        assert r.status_code == 400
        assert r.json()["detail"] == "Could not read this audio file"

    def test_too_big(self, admin):
        r = up(admin, "/tmp/big.bin", "b.mp3")
        assert r.status_code == 400
        assert "10 MB" in r.json()["detail"]

    def test_unauth(self):
        with open("/tmp/long.mp3", "rb") as f:
            r = requests.post(f"{API}/settings/seller-voice", files={"file": ("s.mp3", f, "audio/mpeg")}, timeout=60)
        assert r.status_code in (401, 403)


# --- valid flow + isolation + clone engine
class TestSellerVoiceFlow:
    def test_valid_upload_persist_isolation_clone(self, admin, other):
        t0 = time.time()
        r = up(admin, "/tmp/long.mp3")
        TIMINGS["upload"] = time.time() - t0
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d["media_id"], str) and d["media_id"]
        assert 16 <= d["seconds"] <= 18.5
        assert len(d["text"]) > 0
        print("transcript:", d["text"], "upload s:", TIMINGS["upload"])
        s = requests.get(f"{API}/settings", headers=H(admin), timeout=30).json()
        assert s["seller_voice_media_id"] == d["media_id"]
        assert s["seller_voice_text"] == d["text"]
        # owner fetch
        m = requests.get(f"{API}/media/{d['media_id']}", params={"auth": admin}, timeout=60)
        assert m.status_code == 200 and m.headers["content-type"].startswith("audio/wav")
        # no auth -> 401, other tenant -> 404
        assert requests.get(f"{API}/media/{d['media_id']}", timeout=60).status_code == 401
        assert requests.get(f"{API}/media/{d['media_id']}", params={"auth": other}, timeout=60).status_code == 404
        # clone engine
        t0 = time.time()
        v = requests.post(f"{API}/voice/test", headers=H(admin), json={"text": KM}, timeout=70)
        TIMINGS["clone"] = time.time() - t0
        print("clone test:", v.status_code, round(TIMINGS["clone"], 1), v.text[:200])
        assert v.status_code in (200, 502)
        assert v.headers["content-type"].startswith("application/json")
        if v.status_code == 200:
            assert v.json()["engine"] == "voxcpm2-hf-clone"
        else:
            assert "busy or down" in v.json()["detail"]
        assert TIMINGS["clone"] < 58

    def test_cross_tenant_media_id_injection(self, admin, other):
        """Business B should not be able to point its seller voice at A's media id via PUT /settings"""
        a_mid = requests.get(f"{API}/settings", headers=H(admin), timeout=30).json()["seller_voice_media_id"]
        if not a_mid:
            pytest.skip("no admin sample")
        sb = requests.get(f"{API}/settings", headers=H(other), timeout=30).json()
        orig = sb.get("seller_voice_media_id", "")
        sb["seller_voice_media_id"] = a_mid
        r = requests.put(f"{API}/settings", headers=H(other), json=sb, timeout=30)
        after = requests.get(f"{API}/settings", headers=H(other), timeout=30).json()["seller_voice_media_id"]
        # restore
        requests.delete(f"{API}/settings/seller-voice", headers=H(other), timeout=30)
        assert after != a_mid, f"PUT /settings accepted another tenant's seller_voice_media_id (status {r.status_code})"

    def test_delete_then_default_engine(self, admin):
        r = requests.delete(f"{API}/settings/seller-voice", headers=H(admin), timeout=30)
        assert r.status_code == 200 and r.json()["ok"] is True
        s = requests.get(f"{API}/settings", headers=H(admin), timeout=30).json()
        assert s["seller_voice_media_id"] == "" and s["seller_voice_text"] == ""
        t0 = time.time()
        v = requests.post(f"{API}/voice/test", headers=H(admin), json={"text": KM}, timeout=70)
        TIMINGS["default"] = time.time() - t0
        print("default test:", v.status_code, round(TIMINGS["default"], 1), v.text[:200])
        assert v.status_code in (200, 502)
        assert v.headers["content-type"].startswith("application/json")
        if v.status_code == 200:
            assert v.json()["engine"] == "voxcpm2-hf"
        assert TIMINGS["default"] < 58

    def test_english_openai(self, admin):
        v = requests.post(f"{API}/voice/test", headers=H(admin), json={"text": "Hi, thanks for your message!"}, timeout=70)
        assert v.status_code == 200, v.text
        assert v.json()["engine"] == "openai"


# --- widget async voice
class TestWidgetVoice:
    def test_widget_voice_background(self, admin):
        sid = f"TEST_web-{uuid.uuid4()}"
        t0 = time.time()
        with open("/tmp/vox_km.mp3", "rb") as f:
            r = requests.post(f"{API}/public/default/voice", data={"session_id": sid, "name": "TEST voice"},
                              files={"file": ("v.mp3", f, "audio/mpeg")}, timeout=30)
        accept_t = time.time() - t0
        assert r.status_code == 200 and r.json() == {"accepted": True}
        assert accept_t < 10, f"accept took {accept_t}"
        user_seen = ai = None
        for _ in range(60):
            time.sleep(2)
            msgs = requests.get(f"{API}/public/default/chat/{sid}", timeout=30).json()["messages"]
            if msgs and user_seen is None:
                user_seen = time.time() - t0
            ais = [m for m in msgs if m["role"] == "ai"]
            if ais:
                ai = ais[-1]
                break
        total = time.time() - t0
        print(f"accept {accept_t:.1f}s user msg {user_seen}s ai {total:.1f}s; ai atts {ai and ai.get('attachments')}; text {ai and ai['text'][:120]}")
        assert user_seen is not None
        assert msgs[0]["role"] == "user" and msgs[0]["text"] not in ("", "(voice message)")
        assert ai is not None, "no AI reply within 120 s"
        audio = [a for a in ai.get("attachments", []) if a["type"] == "audio"]
        if audio:
            assert audio[0]["engine"] in ("voxcpm2-hf", "voxcpm2-hf-clone", "openai")
