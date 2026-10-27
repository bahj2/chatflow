# Iteration 30: free trial = Pro features minus voice-to-voice; tour video static asset
import os
import sys
import uuid
import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def shop():
    email = f"TEST_trial_{uuid.uuid4().hex[:8]}@example.com".lower()
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "TestPass123!", "business_name": "TEST_Trial Shop"})
    assert r.status_code in (200, 201), r.text
    d = r.json()
    tok = d.get("token") or d.get("access_token")
    s = requests.Session()
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    yield {"s": s, "email": email, "data": d}
    # cleanup
    try:
        from pymongo import MongoClient
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        u = db.users.find_one({"email": email})
        if u:
            bid = u["business_id"]
            for c in ("subscriptions", "settings", "businesses", "notion_links", "notion_docs", "conversations", "messages", "products", "ai_usage"):
                db[c].delete_many({"business_id": bid})
            db.businesses.delete_many({"id": bid})
            db.users.delete_many({"business_id": bid})
    except Exception as e:
        print("cleanup failed", e)


# Billing view for a brand-new shop
def test_trial_billing_view(shop):
    r = shop["s"].get(f"{API}/billing")
    assert r.status_code == 200, r.text
    sub = r.json()["sub"]
    assert sub["plan"] == "trial"
    assert sub["pro"] is True
    assert sub["voice"] is False
    assert sub["team"] == 3
    assert sub["limit"] == 200
    assert sub["days_left"] == 14
    assert sub["active"] is True and sub["paused"] is False


# Pro-only Notion endpoints are no longer 402 for trial
def test_trial_notion_connect_not_402(shop):
    r = shop["s"].post(f"{API}/notion/connect", json={"token": "bad-token"})
    assert r.status_code != 402, r.text
    assert r.status_code in (400, 422)


def test_trial_notion_sync_not_402(shop):
    r = shop["s"].post(f"{API}/notion/sync")
    assert r.status_code != 402, r.text
    assert r.status_code == 400  # Connect Notion first


def test_trial_notion_status(shop):
    r = shop["s"].get(f"{API}/notion")
    assert r.status_code == 200 and r.json()["connected"] is False


# Voice-to-voice stays paid-only
def test_trial_voice_test_402(shop):
    r = shop["s"].post(f"{API}/voice/test", json={"text": "hello"})
    assert r.status_code == 402, r.text
    assert "paid Pro and Business" in r.json()["detail"]


def test_trial_seller_voice_402(shop):
    files = {"file": ("v.wav", b"RIFF0000WAVEfmt " + b"\x00" * 64, "audio/wav")}
    r = shop["s"].post(f"{API}/settings/seller-voice", files=files, data={"text": "hi"})
    assert r.status_code == 402, r.text
    assert "paid Pro and Business" in r.json()["detail"]


# effective() unit: strips voice for trial, keeps for pro
def test_effective_unit():
    import billing as B
    from core import Settings
    from datetime import timedelta
    s = Settings(voice_replies=True, seller_voice_media_id="m1", seller_voice_text="t")
    t = B.now()
    mk = lambda plan: {"plan": plan, "period_start": B.iso(t), "period_end": B.iso(t + timedelta(days=14)), "paid_until": B.iso(t + timedelta(days=14)),
                       "used": 0, "limit": 200, "extra": 0, "exempt": False}
    vt = B.view(mk("trial"))
    assert vt["pro"] is True and vt["voice"] is False
    e = B.effective(s, vt)
    assert e.voice_replies is False and e.seller_voice_media_id == "" and e.seller_voice_text == ""
    vp = B.view(mk("pro"))
    assert B.effective(s, vp).voice_replies is True
    vs = B.view(mk("starter"))
    assert vs["pro"] is False and vs["voice"] is False
    # expired trial -> no pro
    exp = mk("trial"); exp["paid_until"] = B.iso(t - timedelta(days=1))
    ve = B.view(exp)
    assert ve["pro"] is False and ve["voice"] is False and ve["team"] == 1


# Static tour video and poster
def test_tour_video_served():
    r = requests.get(f"{BASE_URL}/videos/replyflow-tour.mp4", headers={"Range": "bytes=0-1023"}, timeout=30)
    assert r.status_code in (200, 206)
    assert "video/mp4" in r.headers.get("content-type", "")


def test_tour_poster_served():
    r = requests.get(f"{BASE_URL}/videos/replyflow-tour.jpg", timeout=30)
    assert r.status_code == 200 and "image" in r.headers.get("content-type", "")
