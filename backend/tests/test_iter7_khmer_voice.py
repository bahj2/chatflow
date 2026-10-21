# Iteration 7: Khmer voice fixes — Gemini Khmer STT, Microsoft Khmer TTS (edge-tts), spoken replies, khmer_voice setting
import asyncio
import difflib
import os
import re
import sys
import uuid

import pytest
import requests

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402

load_dotenv("/app/backend/.env")
import media as M  # noqa: E402
from pymongo import MongoClient  # noqa: E402

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
FX = "/tmp/rf_fixtures"
T = 180
KH = re.compile(r"[\u1780-\u17FF]")
LATIN = re.compile(r"[A-Za-z]")
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF]")
SID = f"TEST_iter7_{uuid.uuid4().hex[:6]}"
RESULTS = {}


def kh_only(t):
    return "".join(c for c in t if "\u1780" <= c <= "\u17ff")


@pytest.fixture(scope="module")
def sun():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "loadtest+706ab4fd@example.com", "password": "loadtest123"}, timeout=20)
    if r.status_code != 200:
        pytest.skip("login failed")
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    bid = r.json()["user"]["business_id"]
    orig = requests.get(f"{BASE_URL}/api/settings", headers=h, timeout=20).json()
    # ensure voice replies on, no voxcpm
    s = dict(orig, voice_replies=True, voxcpm_url="", khmer_voice="sreymom")
    assert requests.put(f"{BASE_URL}/api/settings", headers=h, json=s, timeout=20).status_code == 200
    yield h, bid, s
    requests.put(f"{BASE_URL}/api/settings", headers=h, json=orig, timeout=20)
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    convs = [c["id"] for c in db.conversations.find({"business_id": bid, "external_id": {"$regex": "^TEST_iter7"}}, {"id": 1})]
    db.messages.delete_many({"conversation_id": {"$in": convs}})
    db.conversations.delete_many({"id": {"$in": convs}})
    print("cleaned convs", len(convs))


def voice(bid, fname, sid, ip):
    with open(f"{FX}/{fname}", "rb") as f:
        r = requests.post(f"{BASE_URL}/api/public/{bid}/voice", data={"session_id": sid, "name": "TEST Khmer"},
                          files={"file": (fname, f, "audio/mpeg")}, headers={"X-Forwarded-For": ip}, timeout=T)
    assert r.status_code == 200, r.text
    return r.json()["reply"]


def history(bid, sid):
    return requests.get(f"{BASE_URL}/api/public/{bid}/chat/{sid}", timeout=30).json()["messages"]


# ---- Khmer voice in -> Khmer transcript; Khmer voice out via Microsoft ----
def test_khmer_voice_roundtrip(sun):
    h, bid, _ = sun
    sid = SID + "_km"
    reply = voice(bid, "khmer_q.mp3", sid, "10.77.1.1")
    msgs = history(bid, sid)
    user_text = msgs[0]["text"]
    print("TRANSCRIPT:", user_text)
    print("REPLY:", reply["text"])
    assert KH.search(user_text), f"transcript not Khmer: {user_text}"
    assert len(kh_only(user_text)) >= 0.6 * len(user_text.replace(" ", "").replace("?", "")), user_text
    assert difflib.SequenceMatcher(None, kh_only(user_text), kh_only("សួស្តីបង បងមានលក់អីដែរ?")).ratio() > 0.6
    assert KH.search(reply["text"]), "reply not Khmer"
    assert not EMOJI.search(reply["text"]), "emoji in spoken reply"
    assert "$" not in reply["text"], "$ in spoken reply"
    audio = [a for a in reply["attachments"] if a["type"] == "audio"]
    assert audio and audio[0]["engine"] == "microsoft", reply["attachments"]
    r = requests.get(f"{BASE_URL}/api/media/{audio[0]['media_id']}", timeout=60)
    assert r.status_code == 200 and r.headers["content-type"].startswith("audio/mpeg")
    heard = asyncio.run(M.transcribe(r.content))
    ratio = difflib.SequenceMatcher(None, kh_only(reply["text"]), kh_only(heard)).ratio()
    print("HEARD BACK:", heard, "ratio", round(ratio, 2))
    RESULTS["km_ratio"] = ratio
    assert ratio > 0.6
    latin = LATIN.findall(reply["text"])
    print("latin chars in reply:", len(latin))


# ---- English voice still works via OpenAI tts-1 ----
def test_english_voice_roundtrip(sun):
    _, bid, _ = sun
    sid = SID + "_en"
    reply = voice(bid, "english_q.mp3", sid, "10.77.1.2")
    user_text = history(bid, sid)[0]["text"]
    print("EN TRANSCRIPT:", user_text, "| REPLY:", reply["text"])
    assert "latte" in user_text.lower() or "coffee" in user_text.lower()
    assert not KH.search(user_text)
    audio = [a for a in reply["attachments"] if a["type"] == "audio"]
    assert audio and audio[0]["engine"] == "openai"


# ---- typed Khmer text -> text reply only ----
def test_typed_khmer_text_no_audio(sun):
    _, bid, _ = sun
    r = requests.post(f"{BASE_URL}/api/public/{bid}/chat", json={"session_id": SID + "_txt", "text": "សួស្តីបង មានកាហ្វេអ្វីខ្លះ?"},
                      headers={"X-Forwarded-For": "10.77.1.3"}, timeout=T)
    assert r.status_code == 200
    rep = r.json()["reply"]
    print("TYPED REPLY:", rep["text"])
    assert KH.search(rep["text"])
    assert not [a for a in rep.get("attachments", []) if a["type"] == "audio"]


# ---- /api/voice/test routing + khmer_voice setting ----
def test_voice_test_khmer_and_piseth(sun):
    h, _, s = sun
    km = "សួស្តីបង! អរគុណសម្រាប់សាររបស់បង។"
    r1 = requests.post(f"{BASE_URL}/api/voice/test", headers=h, json={"text": km}, timeout=T)
    assert r1.status_code == 200 and r1.json()["engine"] == "microsoft"
    a1 = requests.get(f"{BASE_URL}/api/media/{r1.json()['media_id']}", timeout=60)
    assert a1.headers["content-type"].startswith("audio/mpeg")
    r = requests.put(f"{BASE_URL}/api/settings", headers=h, json=dict(s, khmer_voice="piseth"), timeout=20)
    assert r.status_code == 200 and r.json()["khmer_voice"] == "piseth"
    assert requests.get(f"{BASE_URL}/api/settings", headers=h, timeout=20).json()["khmer_voice"] == "piseth"
    r2 = requests.post(f"{BASE_URL}/api/voice/test", headers=h, json={"text": km}, timeout=T)
    assert r2.status_code == 200 and r2.json()["engine"] == "microsoft"
    a2 = requests.get(f"{BASE_URL}/api/media/{r2.json()['media_id']}", timeout=60)
    assert a1.content != a2.content
    requests.put(f"{BASE_URL}/api/settings", headers=h, json=s, timeout=20)


def test_voice_test_english_openai(sun):
    h, _, _ = sun
    r = requests.post(f"{BASE_URL}/api/voice/test", headers=h, json={"text": "Hi there, thanks for your message!"}, timeout=T)
    assert r.status_code == 200 and r.json()["engine"] == "openai"


def test_voice_test_emoji_only_khmer(sun):
    h, _, _ = sun
    r = requests.post(f"{BASE_URL}/api/voice/test", headers=h, json={"text": "សួស្តី 😊🙏"}, timeout=T)
    assert r.status_code == 200 and r.json()["engine"] == "microsoft"


def test_bogus_voxcpm_falls_back_microsoft(sun):
    h, _, s = sun
    requests.put(f"{BASE_URL}/api/settings", headers=h, json=dict(s, voxcpm_url="http://127.0.0.1:9", voxcpm_for="khmer"), timeout=20)
    try:
        r = requests.post(f"{BASE_URL}/api/voice/test", headers=h, json={"text": "សួស្តីបង"}, timeout=T)
        assert r.status_code == 200 and r.json()["engine"] == "microsoft"
    finally:
        requests.put(f"{BASE_URL}/api/settings", headers=h, json=s, timeout=20)


def test_invalid_khmer_voice_value(sun):
    # unknown khmer_voice value should not break TTS (falls back to sreymom)
    h, _, s = sun
    r = requests.put(f"{BASE_URL}/api/settings", headers=h, json=dict(s, khmer_voice="bogus"), timeout=20)
    print("bogus khmer_voice PUT status", r.status_code)
    try:
        r2 = requests.post(f"{BASE_URL}/api/voice/test", headers=h, json={"text": "សួស្តីបង"}, timeout=T)
        assert r2.status_code == 200 and r2.json()["engine"] == "microsoft"
    finally:
        requests.put(f"{BASE_URL}/api/settings", headers=h, json=s, timeout=20)
