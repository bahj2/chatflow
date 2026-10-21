# Iteration 10: Notion knowledge feature (connect/sync/disconnect, cron, isolation, AI usage)
import os
import re
import subprocess
import time
import uuid

import pytest
import requests
from dotenv import dotenv_values

FE = dotenv_values("/app/frontend/.env")
BASE_URL = FE["REACT_APP_BACKEND_URL"].rstrip("/")
CRON_SECRET = dotenv_values("/app/backend/.env")["WEBHOOK_CRON_SECRET"]
ADMIN = ("admin@replyflow.com", "admin123")
LOAD = ("loadtest+706ab4fd@example.com", "loadtest123")


def login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


def seed_admin():
    out = subprocess.run(["python3", "/app/scripts/notion_mock_sync.py", ADMIN[0]], capture_output=True, text=True, timeout=120)
    assert "status: ok" in out.stdout, out.stdout + out.stderr
    return out.stdout


@pytest.fixture(scope="module")
def admin():
    seed_admin()
    return login(*ADMIN)


@pytest.fixture(scope="module")
def load():
    s = login(*LOAD)
    s.delete(f"{BASE_URL}/api/notion")
    return s


# --- seed script / sync logic
def test_seed_script_output():
    out = seed_admin()
    assert "pages: 4" in out
    assert "Sunday 8:00–12:00" in out
    assert "Riverside | #12 Sisowath Quay" in out
    assert "Durian Smoothie" in out and "In stock: no" in out
    first = int(re.search(r"first sync: (\d+)", out).group(1))
    second = int(re.search(r"cached\) sync: (\d+)", out).group(1))
    assert second < first


# --- GET /api/notion
def test_get_notion_connected_view(admin):
    r = admin.get(f"{BASE_URL}/api/notion")
    assert r.status_code == 200
    d = r.json()
    assert d["connected"] is True and d["status"] == "ok"
    assert d["workspace"] == "Sunrise Coffee" and d["hint"] == "3456"
    assert d["page_count"] == 4 and len(d["pages"]) == 4
    kinds = [p["kind"] for p in d["pages"]]
    assert kinds == ["page", "page", "row", "row"]
    for p in d["pages"]:
        assert set(p) >= {"title", "url", "kind", "chars"}
    raw = r.text
    assert "token_enc" not in raw and "ntn_mocktoken" not in raw and "knowledge" not in raw
    assert "Sisowath" not in raw and "palmtree" not in raw


def test_get_notion_not_connected(load):
    r = load.get(f"{BASE_URL}/api/notion")
    assert r.status_code == 200 and r.json() == {"connected": False}


def test_get_notion_requires_auth():
    assert requests.get(f"{BASE_URL}/api/notion", timeout=20).status_code == 401


# --- POST /api/notion/connect
def test_connect_non_notion_text(load):
    r = load.post(f"{BASE_URL}/api/notion/connect", json={"token": "hello-world-not-a-secret"})
    assert r.status_code == 400 and "doesn't look like a Notion secret" in r.json()["detail"]


def test_connect_short_body_422(load):
    r = load.post(f"{BASE_URL}/api/notion/connect", json={"token": "ntn_1"})
    assert r.status_code == 422


def test_connect_fake_token_rejected(load):
    r = load.post(f"{BASE_URL}/api/notion/connect", json={"token": "ntn_fakefakefake12345"})
    assert r.status_code == 400, r.text
    assert "Notion rejected this secret" in r.json()["detail"], r.text
    assert load.get(f"{BASE_URL}/api/notion").json() == {"connected": False}


# --- POST /api/notion/sync
def test_sync_not_connected(load):
    r = load.post(f"{BASE_URL}/api/notion/sync")
    assert r.status_code == 400 and r.json()["detail"] == "Connect Notion first"


def test_sync_invalid_secret_keeps_pages(admin):
    r = admin.post(f"{BASE_URL}/api/notion/sync")
    assert r.status_code == 200
    assert r.json()["status"] in ("queued", "syncing")
    d = None
    for _ in range(20):
        time.sleep(1.5)
        d = admin.get(f"{BASE_URL}/api/notion").json()
        if d["status"] not in ("queued", "syncing"):
            break
    assert d["status"] == "invalid", d
    assert "Notion rejected this secret" in d["last_error"]
    assert d["page_count"] == 4 and len(d["pages"]) == 4
    seed_admin()


# --- isolation + AI knowledge
def test_isolation_load_business(load, admin):
    assert load.get(f"{BASE_URL}/api/notion").json() == {"connected": False}
    r = load.post(f"{BASE_URL}/api/ai/test", json={"text": "What is the address of your Riverside branch?"}, timeout=90)
    assert r.status_code == 200
    assert "Sisowath" not in r.json()["reply"], r.json()["reply"]


def test_ai_uses_notion_english(admin):
    r = admin.post(f"{BASE_URL}/api/ai/test", json={"text": "Are you open on Sunday afternoon? How much is the durian smoothie?"}, timeout=90)
    assert r.status_code == 200
    reply = r.json()["reply"]
    print("EN reply:", reply)
    assert "3.5" in reply
    assert re.search(r"12|noon|morning", reply, re.I)
    assert re.search(r"out of stock|not available|unavailable|sold out", reply, re.I)


def test_ai_uses_notion_khmer(admin):
    r = admin.post(f"{BASE_URL}/api/ai/test", json={"text": "តើសាខា Riverside នៅឯណា?"}, timeout=90)
    assert r.status_code == 200
    reply = r.json()["reply"]
    print("KM reply:", reply)
    assert "12" in reply and ("Sisowath" in reply or "ស៊ីសុវត្ថិ" in reply)


def test_widget_chat_uses_notion(admin):
    bid = admin.get(f"{BASE_URL}/api/auth/me").json()
    bid = bid.get("business_id") or bid.get("user", {}).get("business_id")
    sid = f"TEST_{uuid.uuid4().hex[:10]}"
    r = requests.post(f"{BASE_URL}/api/public/{bid}/chat", json={"session_id": sid, "text": "How much is the Durian Smoothie?"}, timeout=90)
    assert r.status_code == 200, r.text
    print("widget:", r.text[:400])
    assert "3.5" in r.text


def test_suggest_uses_notion(admin):
    convs = admin.get(f"{BASE_URL}/api/conversations").json()
    items = convs if isinstance(convs, list) else convs.get("items") or convs.get("conversations") or []
    web = [c for c in items if str(c.get("external_id", "")).startswith("TEST_")] or items
    if not web:
        pytest.skip("no conversation")
    r = admin.post(f"{BASE_URL}/api/conversations/{web[0]['id']}/suggest", timeout=90)
    assert r.status_code == 200
    print("suggest:", r.json())
    assert isinstance(r.json()["suggestions"], list) and r.json()["suggestions"]


def test_disconnect_removes_knowledge(admin):
    r = admin.delete(f"{BASE_URL}/api/notion")
    assert r.status_code == 200 and r.json() == {"connected": False}
    assert admin.get(f"{BASE_URL}/api/notion").json() == {"connected": False}
    r = admin.post(f"{BASE_URL}/api/ai/test", json={"text": "What is the address of your Riverside branch and the durian smoothie price?"}, timeout=90)
    reply = r.json()["reply"]
    print("after disconnect:", reply)
    assert "Sisowath" not in reply
    seed_admin()


# --- cron
def test_cron_no_auth():
    r = requests.post(f"{BASE_URL}/api/cron/notion-sync", json={"event": "x", "run_id": "a", "data": None}, timeout=20)
    assert r.status_code == 401


def test_cron_wrong_auth():
    r = requests.post(f"{BASE_URL}/api/cron/notion-sync", headers={"Authorization": "Bearer wrong"}, json={"event": "x"}, timeout=20)
    assert r.status_code == 401


def test_cron_ok_and_duplicate():
    wid = f"TEST_{uuid.uuid4()}"
    h = {"Authorization": f"Bearer {CRON_SECRET}", "X-Webhook-Id": wid}
    body = {"event": "cron.notion-sync", "run_id": wid, "data": None}
    t = time.time()
    r = requests.post(f"{BASE_URL}/api/cron/notion-sync", headers=h, json=body, timeout=20)
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert time.time() - t < 5
    r2 = requests.post(f"{BASE_URL}/api/cron/notion-sync", headers=h, json=body, timeout=20)
    assert r2.status_code == 200 and r2.json() == {"ok": True, "duplicate": True}


def test_cron_non_json():
    h = {"Authorization": f"Bearer {CRON_SECRET}", "Content-Type": "application/json"}
    r = requests.post(f"{BASE_URL}/api/cron/notion-sync", headers=h, data="not json", timeout=20)
    assert r.status_code == 400


def test_final_reseed_admin():
    # cron above would mark admin 'invalid' (mock secret vs real Notion); restore demo state
    time.sleep(6)
    seed_admin()
    s = login(*ADMIN)
    assert s.get(f"{BASE_URL}/api/notion").json()["status"] == "ok"
