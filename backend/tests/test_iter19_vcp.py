# Iteration 19: Voice Creator Pro (VoxCPM2) connect/voice/test/refresh/disconnect + regressions
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
TUNNEL = os.environ.get("VCP_TUNNEL", "https://studios-sectors-saver-list.trycloudflare.com")
MOCK = "http://localhost:8199"
KM = "សួស្តីបង! អរគុណដែលបានទាក់ទងមកហាងយើងខ្ញុំ។"


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def H():
    h = login("vcp-test@example.com", "vcptest123")
    yield h
    requests.delete(f"{API}/voice/vcp", headers=h, timeout=30)  # leave disconnected for UI tests


def last_call():
    return requests.get(f"{MOCK}/_calls", timeout=10).json()[-1]


# --- connect validation
def test_connect_http_rejected(H):
    r = requests.post(f"{API}/voice/vcp/connect", headers=H, json={"url": "http://example.com", "key": "x"}, timeout=30)
    assert r.status_code == 400 and "https" in r.json()["detail"]


def test_connect_loopback_rejected(H):
    r = requests.post(f"{API}/voice/vcp/connect", headers=H, json={"url": "https://127.0.0.1:8199", "key": "x"}, timeout=30)
    assert r.status_code == 400 and "private" in r.json()["detail"]


def test_connect_not_vcp(H):
    r = requests.post(f"{API}/voice/vcp/connect", headers=H, json={"url": "https://example.com", "key": "x"}, timeout=60)
    assert r.status_code == 424 and "does not answer like Voice Creator Pro" in r.json()["detail"]


def test_connect_wrong_key(H):
    r = requests.post(f"{API}/voice/vcp/connect", headers=H, json={"url": TUNNEL, "key": "bad"}, timeout=60)
    assert r.status_code == 424 and "Wrong API key" in r.json()["detail"]


def test_only_vcp_without_connection(H):
    requests.delete(f"{API}/voice/vcp", headers=H, timeout=30)
    r = requests.post(f"{API}/voice/test", headers=H, json={"text": KM, "only_vcp": True}, timeout=60)
    assert r.status_code == 400


def test_refresh_without_connection(H):
    r = requests.post(f"{API}/voice/vcp/refresh", headers=H, timeout=30)
    assert r.status_code == 400


def test_connect_ok(H):
    r = requests.post(f"{API}/voice/vcp/connect", headers=H, json={"url": TUNNEL + "/", "key": "test-key"}, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["connected"] is True and d["url"] == TUNNEL and d["model"] == "voxcpm2"
    assert [v["id"] for v in d["voices"]] == ["v_rasmey", "v_narrator"]
    assert "key" not in d and "vcp_key" not in d


# --- settings never leak key, PUT cannot alter vcp fields
def test_settings_hide_key_and_protect_fields(H):
    s = requests.get(f"{API}/settings", headers=H, timeout=30).json()
    assert "vcp_key" not in s and s["vcp_url"] == TUNNEL
    assert "khmer_voice" not in s and "voxcpm_url" not in s
    bad = {**s, "vcp_url": "https://evil.example.com", "vcp_voice_id": "hack", "vcp_voices": [{"id": "hack", "name": "x"}], "vcp_key": "stolen"}
    r = requests.put(f"{API}/settings", headers=H, json=bad, timeout=30)
    assert r.status_code == 200, r.text
    assert "vcp_key" not in r.json()
    s2 = requests.get(f"{API}/settings", headers=H, timeout=30).json()
    assert s2["vcp_url"] == TUNNEL and s2["vcp_voice_id"] == s["vcp_voice_id"] and len(s2["vcp_voices"]) == 2
    # key still works -> test uses stored key
    r = requests.post(f"{API}/voice/test", headers=H, json={"text": KM, "only_vcp": True}, timeout=90)
    assert r.status_code == 200, r.text


# --- voice pick
def test_voice_pick(H):
    assert requests.put(f"{API}/voice/vcp/voice", headers=H, json={"voice_id": "nope"}, timeout=30).status_code == 400
    r = requests.put(f"{API}/voice/vcp/voice", headers=H, json={"voice_id": "v_rasmey"}, timeout=30)
    assert r.status_code == 200 and r.json()["voice_id"] == "v_rasmey"
    assert requests.get(f"{API}/settings", headers=H, timeout=30).json()["vcp_voice_id"] == "v_rasmey"


def test_only_vcp_clone_voice_id(H):
    r = requests.post(f"{API}/voice/test", headers=H, json={"text": KM, "only_vcp": True}, timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["engine"] == "voxcpm2-vcp"
    c = last_call()
    assert c["mode"] == "clone" and c["voice_id"] == "v_rasmey" and c["sync"] == "true" and c["model_family"] == "voxcpm2"
    m = requests.get(f"{API}/media/{d['media_id']}", headers=H, timeout=60)
    assert m.status_code == 200 and m.headers["content-type"].startswith("audio/") and len(m.content) > 1000


def test_general_khmer_uses_vcp_and_english_openai(H):
    r = requests.post(f"{API}/voice/test", headers=H, json={"text": KM}, timeout=90)
    assert r.status_code == 200 and r.json()["engine"] == "voxcpm2-vcp", r.text
    r = requests.post(f"{API}/voice/test", headers=H, json={"text": "Hello, thanks for your order!"}, timeout=90)
    assert r.status_code == 200 and r.json()["engine"] == "openai", r.text


def test_default_voice_with_seller_sample(H):
    r = requests.put(f"{API}/voice/vcp/voice", headers=H, json={"voice_id": ""}, timeout=30)
    assert r.status_code == 200 and r.json()["voice_id"] == ""
    s = requests.get(f"{API}/settings", headers=H, timeout=30).json()
    r = requests.post(f"{API}/voice/test", headers=H, json={"text": KM, "only_vcp": True}, timeout=90)
    assert r.status_code == 200, r.text
    c = last_call()
    if s.get("seller_voice_media_id"):
        assert c["mode"] == "clone" and c["ref_audio_bytes"] > 0 and "voice_id" not in c
        # 10 s sample <= 15 s -> ref_text kept
        assert c["ref_text"] == s["seller_voice_text"]
        assert c["ref_audio_bytes"] <= 16000 * 2 * 15 + 1000
    else:
        assert c["mode"] == "design" and c["instruct_text"]


def test_refresh_keeps_voice(H):
    requests.put(f"{API}/voice/vcp/voice", headers=H, json={"voice_id": "v_narrator"}, timeout=30)
    r = requests.post(f"{API}/voice/vcp/refresh", headers=H, timeout=60)
    assert r.status_code == 200, r.text
    assert r.json()["voice_id"] == "v_narrator" and len(r.json()["voices"]) == 2


def test_disconnect(H):
    r = requests.delete(f"{API}/voice/vcp", headers=H, timeout=30)
    assert r.status_code == 200 and r.json()["connected"] is False
    s = requests.get(f"{API}/settings", headers=H, timeout=30).json()
    assert s["vcp_url"] == "" and s["vcp_voice_id"] == "" and s["vcp_voices"] == []
    assert requests.post(f"{API}/voice/vcp/refresh", headers=H, timeout=30).status_code == 400


# --- regressions
def test_old_endpoints_gone(H):
    for p in ("/voice/voxcpm-check", "/voice/voxcpm-pair", "/voice/voxcpm-pair/start"):
        assert requests.post(f"{API}{p}", headers=H, json={}, timeout=30).status_code in (404, 405)
        assert requests.get(f"{API}{p}", headers=H, timeout=30).status_code in (404, 405)


def test_admin_basic_flows():
    h = login("admin@replyflow.com", "admin123")
    for p in ("/auth/me", "/products", "/orders", "/conversations", "/settings"):
        r = requests.get(f"{API}{p}", headers=h, timeout=30)
        assert r.status_code == 200, f"{p} {r.status_code}"
