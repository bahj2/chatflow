# Iteration 5: verify fixes from iteration_4 (telegram webhook, strict status, pagination cursor, summary language)
import os
import re
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
ADMIN_BID = "da4f34c0-2f00-41e1-ab8c-86332eada73f"


def login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code} {r.text}")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def admin():
    return login("admin@replyflow.com", "admin123")


@pytest.fixture(scope="module")
def big():
    return login("loadtest+82c7ca04@example.com", "loadtest123")


@pytest.fixture(scope="module")
def lt100():
    return login("loadtest+706ab4fd@example.com", "loadtest123")


# Telegram status for admin (webhook re-pointed)
def test_admin_telegram_connected(admin):
    me = requests.get(f"{BASE_URL}/api/auth/me", headers=admin, timeout=20).json()
    print("admin me:", me)
    r = requests.get(f"{BASE_URL}/api/channels/status", headers=admin, timeout=30)
    assert r.status_code == 200
    tg = r.json()["telegram"]
    print("admin tg:", tg)
    assert tg["configured"] is True
    assert tg["connected"] is True
    assert isinstance(tg["bot"], str) and tg["bot"]


# Strict status for owners without token
@pytest.mark.parametrize("who", ["big", "lt100"])
def test_owner_no_token_not_connected(who, request):
    h = request.getfixturevalue(who)
    tg = requests.get(f"{BASE_URL}/api/channels/status", headers=h, timeout=30).json()["telegram"]
    print(who, tg)
    assert tg["connected"] is False


# Webhook without secret -> 403
def test_admin_webhook_no_secret_403():
    r = requests.post(f"{BASE_URL}/api/webhooks/telegram/{ADMIN_BID}", json={"message": {"text": "hi", "chat": {"id": 1}}}, timeout=20)
    assert r.status_code == 403


def test_admin_webhook_wrong_secret_403():
    r = requests.post(f"{BASE_URL}/api/webhooks/telegram/{ADMIN_BID}", json={"message": {"text": "hi", "chat": {"id": 1}}},
                      headers={"X-Telegram-Bot-Api-Secret-Token": "nope"}, timeout=20)
    assert r.status_code == 403


# Telegram filter on big inbox
def test_big_telegram_filter_first_page(big):
    d = requests.get(f"{BASE_URL}/api/conversations", params={"channel": "telegram"}, headers=big, timeout=30).json()
    print("telegram total", d["total"], len(d["items"]))
    assert len(d["items"]) == 50
    assert d["total"] == 1000
    assert all(c["channel"] == "telegram" for c in d["items"])


# Compound cursor pagination: full walk, no duplicates / gaps
def test_big_full_pagination(big):
    seen, before, before_id, pages = [], None, None, 0
    total = None
    while True:
        p = {"limit": 100}
        if before:
            p.update(before=before, before_id=before_id)
        d = requests.get(f"{BASE_URL}/api/conversations", params=p, headers=big, timeout=30).json()
        total = d["total"]
        seen += [c["id"] for c in d["items"]]
        pages += 1
        if not d["has_more"] or not d["items"]:
            break
        before, before_id = d["items"][-1]["updated_at"], d["items"][-1]["id"]
        assert pages < 100
    print("total", total, "seen", len(seen), "pages", pages)
    assert len(seen) == len(set(seen))
    assert len(seen) == total == 3000


def test_big_telegram_pagination(big):
    seen, cur = [], None
    while True:
        p = {"channel": "telegram", "limit": 50}
        if cur:
            p.update(before=cur[0], before_id=cur[1])
        d = requests.get(f"{BASE_URL}/api/conversations", params=p, headers=big, timeout=30).json()
        seen += [c["id"] for c in d["items"]]
        if not d["has_more"]:
            break
        cur = (d["items"][-1]["updated_at"], d["items"][-1]["id"])
    assert len(seen) == len(set(seen)) == 1000


# Summary language: English conversation -> English summary
def test_summary_english(big):
    d = requests.get(f"{BASE_URL}/api/conversations", params={"limit": 20}, headers=big, timeout=30).json()
    eng = None
    for c in d["items"]:
        msgs = requests.get(f"{BASE_URL}/api/conversations/{c['id']}/messages", headers=big, timeout=30).json()
        user_txt = " ".join(m["text"] for m in msgs if m["role"] == "user")
        if user_txt and re.fullmatch(r"[\x00-\x7F’‘“”—–…]+", user_txt):
            eng = c
            print("english conv", c["id"], user_txt[:150])
            break
    if not eng:
        pytest.skip("no english conv found")
    r = requests.post(f"{BASE_URL}/api/conversations/{eng['id']}/summary", params={"force": "true"}, headers=big, timeout=90)
    assert r.status_code == 200
    s = r.json()
    print("summary", s)
    text = " ".join([s["intent"], s["summary"], s["next_step"]] + s["details"])
    non_ascii = [ch for ch in text if ord(ch) > 0x24F]
    assert len(non_ascii) == 0, f"non-latin chars in summary: {''.join(non_ascii)[:50]}"
    assert re.search(r"\b(the|a|to|and|for|customer|is)\b", text, re.I)
