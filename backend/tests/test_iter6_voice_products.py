# Iteration 6: products, media, AI product picks, voice chat (STT/TTS), VoxCPM2 fallback, messenger voice ingestion
import hashlib
import hmac
import json
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
FX = "/tmp/rf_fixtures"
T = 120


def login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]["business_id"]


@pytest.fixture(scope="module")
def sun():
    return login("loadtest+706ab4fd@example.com", "loadtest123")


@pytest.fixture(scope="module")
def other():
    # fresh isolated test business (used for settings-changing tests)
    email = f"test_iter6_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "test1234", "business_name": "TEST_Iter6 Shop"}, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    print("other business", email, d["user"]["business_id"])
    return {"Authorization": f"Bearer {d['token']}"}, d["user"]["business_id"]


@pytest.fixture(scope="module")
def product(sun):
    h, bid = sun
    with open(f"{FX}/mug.png", "rb") as f:
        r = requests.post(f"{BASE_URL}/api/media/image", headers=h, files={"file": ("mug.png", f, "image/png")}, timeout=T)
    assert r.status_code == 200, r.text
    mid = r.json()["id"]
    r = requests.post(f"{BASE_URL}/api/products", headers=h, json={"name": "TEST_Ceramic Coffee Mug", "price": "$12",
                      "description": "Handmade ceramic coffee mug, 350ml, brown glaze", "image_media_id": mid}, timeout=20)
    assert r.status_code == 200, r.text
    p = r.json()
    yield p
    requests.delete(f"{BASE_URL}/api/products/{p['id']}", headers=h, timeout=20)


# ---- media ----
def test_media_get_image(product):
    r = requests.get(f"{BASE_URL}/api/media/{product['image_media_id']}", timeout=60)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")
    assert r.content[:4] == b"\x89PNG"


def test_media_unknown_404():
    assert requests.get(f"{BASE_URL}/api/media/{uuid.uuid4()}", timeout=30).status_code == 404


def test_media_image_bad_type(sun):
    h, _ = sun
    r = requests.post(f"{BASE_URL}/api/media/image", headers=h, files={"file": ("a.txt", b"hello", "text/plain")}, timeout=30)
    assert r.status_code == 400


def test_media_image_too_big(sun):
    h, _ = sun
    r = requests.post(f"{BASE_URL}/api/media/image", headers=h, files={"file": ("a.png", b"\x00" * (5 * 1024 * 1024 + 10), "image/png")}, timeout=60)
    assert r.status_code == 400


# ---- products CRUD + isolation ----
def test_products_list_and_update(sun, product):
    h, _ = sun
    items = requests.get(f"{BASE_URL}/api/products", headers=h, timeout=20).json()
    assert any(p["id"] == product["id"] for p in items)
    assert all("_id" not in p for p in items)
    body = {"name": "TEST_Ceramic Coffee Mug", "price": "$13", "description": product["description"], "image_media_id": product["image_media_id"]}
    r = requests.put(f"{BASE_URL}/api/products/{product['id']}", headers=h, json=body, timeout=20)
    assert r.status_code == 200 and r.json()["price"] == "$13"
    items = requests.get(f"{BASE_URL}/api/products", headers=h, timeout=20).json()
    assert [p for p in items if p["id"] == product["id"]][0]["price"] == "$13"


def test_products_validation(sun):
    h, _ = sun
    assert requests.post(f"{BASE_URL}/api/products", headers=h, json={"name": ""}, timeout=20).status_code == 422


def test_products_tenant_isolation(other, product, sun):
    oh, _ = other
    assert all(p["id"] != product["id"] for p in requests.get(f"{BASE_URL}/api/products", headers=oh, timeout=20).json())
    r = requests.put(f"{BASE_URL}/api/products/{product['id']}", headers=oh, json={"name": "hacked"}, timeout=20)
    assert r.status_code == 404
    r = requests.delete(f"{BASE_URL}/api/products/{product['id']}", headers=oh, timeout=20)
    print("cross-tenant delete status:", r.status_code, r.text)
    # product must still exist for owner
    items = requests.get(f"{BASE_URL}/api/products", headers=sun[0], timeout=20).json()
    assert any(p["id"] == product["id"] and p["name"] != "hacked" for p in items)


def test_products_cross_tenant_delete_returns_404(other, product):
    r = requests.delete(f"{BASE_URL}/api/products/{product['id']}", headers=other[0], timeout=20)
    assert r.status_code == 404, f"expected 404, got {r.status_code} {r.text}"


# ---- AI picks products ----
def test_ai_test_picks_product(sun, product):
    h, _ = sun
    r = requests.post(f"{BASE_URL}/api/ai/test", headers=h, json={"text": "do you have ceramic coffee mugs? how much?"}, timeout=T)
    assert r.status_code == 200, r.text
    d = r.json()
    print("ai test:", d)
    assert "[[show" not in d["reply"].lower()
    assert any(p["product_id"] == product["id"] and p["media_id"] == product["image_media_id"] for p in d["products"])


def test_public_chat_product_attachment(sun, product):
    _, bid = sun
    sid = f"TEST_web-{uuid.uuid4()}"
    r = requests.post(f"{BASE_URL}/api/public/{bid}/chat", json={"session_id": sid, "text": "Do you sell ceramic coffee mugs?", "name": "TEST_iter6"}, timeout=T)
    assert r.status_code == 200, r.text
    rep = r.json()["reply"]
    print("chat reply:", rep)
    atts = rep["attachments"]
    assert not any(a["type"] == "audio" for a in atts)
    prods = [a for a in atts if a["type"] == "product"]
    assert prods and prods[0]["name"] == "TEST_Ceramic Coffee Mug" and prods[0]["price"] and prods[0]["media_id"]
    assert "[[show" not in rep["text"].lower()


def test_public_chat_unrelated_no_products(sun, product):
    _, bid = sun
    r = requests.post(f"{BASE_URL}/api/public/{bid}/chat", json={"session_id": f"TEST_web-{uuid.uuid4()}", "text": "Do you have free wifi for customers?"}, timeout=T)
    assert r.status_code == 200
    atts = r.json()["reply"]["attachments"]
    print("unrelated atts:", atts, r.json()["reply"]["text"])
    assert atts == []


# ---- voice chat ----
def test_public_voice_with_product(sun, product):
    h, bid = sun
    sid = f"TEST_voice-{uuid.uuid4()}"
    with open(f"{FX}/mug_question.ogg", "rb") as f:
        r = requests.post(f"{BASE_URL}/api/public/{bid}/voice", data={"session_id": sid, "name": "TEST_voice"}, files={"file": ("voice.ogg", f, "audio/ogg")}, timeout=T)
    assert r.status_code == 200, r.text
    rep = r.json()["reply"]
    print("voice reply:", rep)
    audio = [a for a in rep["attachments"] if a["type"] == "audio"]
    assert audio and audio[0]["engine"] == "openai"
    assert any(a["type"] == "product" for a in rep["attachments"])
    hist = requests.get(f"{BASE_URL}/api/public/{bid}/chat/{sid}", timeout=20).json()["messages"]
    user = hist[0]
    print("user transcript:", user["text"])
    assert user["role"] == "user" and "mug" in user["text"].lower()
    assert user["attachments"][0]["type"] == "audio"
    m = requests.get(f"{BASE_URL}/api/media/{audio[0]['media_id']}", timeout=60)
    assert m.status_code == 200 and m.headers["content-type"].startswith("audio/mpeg") and len(m.content) > 1000
    convs = requests.get(f"{BASE_URL}/api/conversations", headers=h, params={"channel": "web", "limit": 50}, timeout=20).json()["items"]
    conv = [c for c in convs if c["external_id"] == sid]
    assert conv and conv[0]["last_message"].startswith("[Voice]")


def test_public_voice_too_big(sun):
    _, bid = sun
    with open(f"{FX}/big.bin", "rb") as f:
        r = requests.post(f"{BASE_URL}/api/public/{bid}/voice", data={"session_id": f"TEST_big-{uuid.uuid4()}"}, files={"file": ("v.webm", f, "audio/webm")}, timeout=T)
    assert r.status_code == 400


def test_voice_rate_limit(other):
    _, bid = other
    sid = f"TEST_rl-{uuid.uuid4()}"
    # pre-consume via text chat (shared bucket), AI off to keep it cheap is not possible -> just count 429
    codes = []
    for i in range(7):
        r = requests.post(f"{BASE_URL}/api/public/{bid}/voice", data={"session_id": sid}, files={"file": ("v.webm", b"", "audio/webm")}, timeout=30)
        codes.append(r.status_code)
    print("rl codes:", codes)
    assert codes[-1] == 429 and codes[0] == 400


# ---- voice settings ----
def test_voice_test_openai(other):
    h, _ = other
    r = requests.post(f"{BASE_URL}/api/voice/test", headers=h, json={"text": "Hello there"}, timeout=T)
    assert r.status_code == 200, r.text
    assert r.json()["engine"] == "openai"


def test_seller_voice_upload(other):
    h, _ = other
    with open(f"{FX}/hours_question.mp3", "rb") as f:
        r = requests.post(f"{BASE_URL}/api/settings/seller-voice", headers=h, files={"file": ("s.mp3", f, "audio/mpeg")}, data={"text": ""}, timeout=T)
    assert r.status_code == 200, r.text
    d = r.json()
    print("seller voice:", d)
    assert d["media_id"] and "saturday" in d["text"].lower()
    s = requests.get(f"{BASE_URL}/api/settings", headers=h, timeout=20).json()
    assert s["seller_voice_media_id"] == d["media_id"]
    m = requests.get(f"{BASE_URL}/api/media/{d['media_id']}", timeout=60)
    assert m.status_code == 200 and m.headers["content-type"].startswith("audio/wav")


def test_seller_voice_bad_audio(other):
    h, _ = other
    r = requests.post(f"{BASE_URL}/api/settings/seller-voice", headers=h, files={"file": ("s.mp3", b"notaudio" * 100, "audio/mpeg")}, timeout=60)
    assert r.status_code == 400


def test_voxcpm_bogus_url_falls_back(other):
    h, _ = other
    s = requests.get(f"{BASE_URL}/api/settings", headers=h, timeout=20).json()
    s.update({"voxcpm_url": "https://127.0.0.1:9/", "voxcpm_for": "khmer", "voice": "onyx"})
    assert requests.put(f"{BASE_URL}/api/settings", headers=h, json=s, timeout=20).status_code == 200
    s2 = requests.get(f"{BASE_URL}/api/settings", headers=h, timeout=20).json()
    assert s2["voxcpm_url"] == "https://127.0.0.1:9/" and s2["voice"] == "onyx"
    r = requests.post(f"{BASE_URL}/api/voice/test", headers=h, json={"text": "សួស្តី! អរគុណសម្រាប់សាររបស់អ្នក។"}, timeout=T)
    assert r.status_code == 200, r.text
    assert r.json()["engine"] == "openai"


def test_voice_replies_off_text_only(other):
    h, bid = other
    s = requests.get(f"{BASE_URL}/api/settings", headers=h, timeout=20).json()
    s["voice_replies"] = False
    requests.put(f"{BASE_URL}/api/settings", headers=h, json=s, timeout=20)
    with open(f"{FX}/hours_question.mp3", "rb") as f:
        r = requests.post(f"{BASE_URL}/api/public/{bid}/voice", data={"session_id": f"TEST_vo-{uuid.uuid4()}"}, files={"file": ("v.mp3", f, "audio/mpeg")}, timeout=T)
    assert r.status_code == 200, r.text
    rep = r.json()["reply"]
    assert rep and rep["text"] and not any(a["type"] == "audio" for a in rep["attachments"])
    s["voice_replies"] = True
    requests.put(f"{BASE_URL}/api/settings", headers=h, json=s, timeout=20)


# ---- messenger voice ingestion ----
def test_messenger_voice_ingestion(other):
    h, bid = other
    s = requests.get(f"{BASE_URL}/api/settings", headers=h, timeout=20).json()
    s.update({"fb_page_token": "TEST_fake_page_token", "fb_app_secret": "TEST_secret", "fb_verify_token": "TEST_verify"})
    requests.put(f"{BASE_URL}/api/settings", headers=h, json=s, timeout=20)
    # upload an audio media to get a public URL
    with open(f"{FX}/hours_question.mp3", "rb") as f:
        sv = requests.post(f"{BASE_URL}/api/settings/seller-voice", headers=h, files={"file": ("s.mp3", f, "audio/mpeg")}, timeout=T).json()
    url = f"{BASE_URL}/api/media/{sv['media_id']}"
    psid = f"TEST{uuid.uuid4().hex[:10]}"
    body = json.dumps({"object": "page", "entry": [{"messaging": [{"sender": {"id": psid}, "message": {"mid": "m1", "attachments": [{"type": "audio", "payload": {"url": url}}]}}]}]}).encode()
    sig = "sha256=" + hmac.new(b"TEST_secret", body, hashlib.sha256).hexdigest()
    r = requests.post(f"{BASE_URL}/api/webhooks/messenger/{bid}", data=body, headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"}, timeout=30)
    assert r.status_code == 200
    bad = requests.post(f"{BASE_URL}/api/webhooks/messenger/{bid}", data=body, headers={"X-Hub-Signature-256": "sha256=bad"}, timeout=30)
    assert bad.status_code == 403
    conv = None
    for _ in range(20):
        time.sleep(3)
        items = requests.get(f"{BASE_URL}/api/conversations", headers=h, params={"channel": "messenger"}, timeout=20).json()["items"]
        conv = next((c for c in items if c["external_id"] == psid), None)
        if conv and conv.get("last_role") == "ai":
            break
    assert conv, "messenger conversation not created"
    msgs = requests.get(f"{BASE_URL}/api/conversations/{conv['id']}/messages", headers=h, timeout=20).json()
    print("messenger msgs:", [(m["role"], m["text"][:60], [a["type"] for a in m["attachments"]]) for m in msgs])
    assert msgs[0]["role"] == "user" and "saturday" in msgs[0]["text"].lower()
    assert any(m["role"] == "ai" and any(a["type"] == "audio" for a in m["attachments"]) for m in msgs)
