"""Iteration 22: env fix sanity, admin login, signup, AI test, admin set plan, teammate (member) restrictions,
member removal/plan-downgrade blocking, token_version invalidation, Mongo-backed signup rate limit."""
# Run serially: pytest tests/test_iter22_team_security.py -n 0
import os
import uuid

import bcrypt
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
STAMP = uuid.uuid4().hex[:6]
COLLS = ("settings", "conversations", "messages", "subscriptions", "invoices", "ai_usage", "media", "products", "orders", "notion_links", "notion_docs")
MEM_EMAIL = f"test_member_{STAMP}@example.com"
OWNER_EMAIL = f"test_owner_{STAMP}@example.com"


def H(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@replyflow.com", "password": "admin123"})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["role"] == "superadmin"
    return r.json()["token"]


@pytest.fixture(scope="module")
def shop(admin):
    DB.rate_hits.delete_many({})
    r = requests.post(f"{API}/auth/register", json={"email": OWNER_EMAIL, "password": "secret123", "business_name": f"TEST_Shop_{STAMP}"})
    assert r.status_code == 200, r.text
    d = r.json()
    yield {"tok": d["token"], "bid": d["user"]["business_id"], "uid": d["user"]["id"]}
    bid = d["user"]["business_id"]
    for c in COLLS:
        DB[c].delete_many({"business_id": bid})
    DB.businesses.delete_one({"id": bid})
    DB.users.delete_many({"business_id": bid})


# --- basics
def test_health_public_plans():
    r = requests.get(f"{API}/public/plans")
    assert r.status_code == 200


def test_admin_businesses(admin):
    r = requests.get(f"{API}/admin/businesses", headers=H(admin))
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_register_and_settings_save(shop):
    u = DB.users.find_one({"id": shop["uid"]})
    assert u["email_verified"] is False and u["role"] == "owner"
    s = requests.get(f"{API}/settings", headers=H(shop["tok"])).json()
    s.update(business_info="TEST we sell shoes, $20-$50", assistant_name="Dara")
    r = requests.put(f"{API}/settings", headers=H(shop["tok"]), json=s)
    assert r.status_code == 200, r.text
    assert requests.get(f"{API}/settings", headers=H(shop["tok"])).json()["assistant_name"] == "Dara"


def test_ai_test(shop):
    r = requests.post(f"{API}/ai/test", headers=H(shop["tok"]), json={"text": "How much are your shoes?"}, timeout=90)
    assert r.status_code == 200, r.text
    print("AI reply:", str(r.json())[:200])


def test_team_add_blocked_on_trial(shop):
    s = requests.get(f"{API}/settings", headers=H(shop["tok"])).json()
    s["allowed_emails"] = [MEM_EMAIL]
    r = requests.put(f"{API}/settings", headers=H(shop["tok"]), json=s)
    assert r.status_code == 402, r.text


def test_admin_set_pro(admin, shop):
    r = requests.post(f"{API}/admin/businesses/{shop['bid']}/plan", headers=H(admin), json={"plan": "pro", "days": 30})
    assert r.status_code == 200, r.text
    b = requests.get(f"{API}/billing", headers=H(shop["tok"])).json()
    print("billing:", str(b)[:300])


@pytest.fixture(scope="module")
def member(shop, admin):
    s = requests.get(f"{API}/settings", headers=H(shop["tok"])).json()
    s.update(allowed_emails=[MEM_EMAIL], bakong_account_id="owner@aclb", bakong_merchant_name="Owner",
             fb_page_token="", fb_app_secret="TESTSECRET", fb_verify_token="TESTVERIFY", khqr_token="rbkTESTTOKEN")
    r = requests.put(f"{API}/settings", headers=H(shop["tok"]), json=s)
    assert r.status_code == 200, r.text
    DB.users.insert_one({"id": str(uuid.uuid4()), "email": MEM_EMAIL, "role": "member", "business_id": shop["bid"],
                         "password_hash": bcrypt.hashpw(b"member123", bcrypt.gensalt()).decode(), "created_at": "x"})
    r = requests.post(f"{API}/auth/login", json={"email": MEM_EMAIL, "password": "member123"})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["role"] == "member"
    return r.json()["token"]


# --- member restrictions
def test_member_get_settings_secrets_blank(member):
    s = requests.get(f"{API}/settings", headers=H(member)).json()
    for k in ("telegram_token", "fb_page_token", "fb_app_secret", "fb_verify_token", "khqr_token"):
        assert s[k] == "", k
    assert s["allowed_emails"] == [MEM_EMAIL]


def test_member_put_cannot_change_owner_fields(member, shop):
    s = requests.get(f"{API}/settings", headers=H(member)).json()
    s.update(allowed_emails=[MEM_EMAIL, "x@y.com"], bakong_account_id="thief@aclb", bakong_merchant_name="Thief",
             bakong_city="Siem Reap", khqr_token="rbkTHIEF", telegram_token="123:abc", fb_app_secret="HACK",
             business_info="TEST member edited", faqs=[{"q": "Open?", "a": "Yes"}])
    r = requests.put(f"{API}/settings", headers=H(member), json=s)
    assert r.status_code == 200, r.text
    assert r.json()["khqr_token"] == "" and r.json()["fb_app_secret"] == ""
    cur = requests.get(f"{API}/settings", headers=H(shop["tok"])).json()
    assert cur["allowed_emails"] == [MEM_EMAIL]
    assert cur["bakong_account_id"] == "owner@aclb" and cur["bakong_merchant_name"] == "Owner" and cur["bakong_city"] == "Phnom Penh"
    assert cur["khqr_token"] == "rbkTESTTOKEN" and cur["fb_app_secret"] == "TESTSECRET" and cur["fb_verify_token"] == "TESTVERIFY"
    assert cur["telegram_token"] == ""
    assert cur["business_info"] == "TEST member edited" and cur["faqs"] == [{"q": "Open?", "a": "Yes"}]


def test_member_owner_only_endpoints_403(member):
    assert requests.post(f"{API}/channels/telegram/connect", headers=H(member), json={"base_url": "https://x"}).status_code == 403
    assert requests.post(f"{API}/notion/connect", headers=H(member), json={"token": "x", "page": "y"}).status_code in (403,)
    assert requests.delete(f"{API}/notion", headers=H(member)).status_code == 403


def test_member_can_use_inbox_products_orders(member):
    for p in ("conversations", "products", "orders", "stats", "billing", "channels/status"):
        r = requests.get(f"{API}/{p}", headers=H(member))
        assert r.status_code == 200, (p, r.status_code, r.text)


def test_member_removed_then_blocked(member, shop):
    cur = requests.get(f"{API}/settings", headers=H(shop["tok"])).json()
    cur["allowed_emails"] = []
    assert requests.put(f"{API}/settings", headers=H(shop["tok"]), json=cur).status_code == 200
    r = requests.get(f"{API}/conversations", headers=H(member))
    assert r.status_code == 401 and "access to this shop was removed" in r.json()["detail"]
    r = requests.post(f"{API}/auth/login", json={"email": MEM_EMAIL, "password": "member123"})
    assert r.status_code == 403 and "access to this shop was removed" in r.json()["detail"]
    # re-add
    cur["allowed_emails"] = [MEM_EMAIL]
    assert requests.put(f"{API}/settings", headers=H(shop["tok"]), json=cur).status_code == 200
    assert requests.post(f"{API}/auth/login", json={"email": MEM_EMAIL, "password": "member123"}).status_code == 200
    assert requests.get(f"{API}/conversations", headers=H(member)).status_code == 200


def test_member_blocked_after_downgrade(member, shop, admin):
    assert requests.post(f"{API}/admin/businesses/{shop['bid']}/plan", headers=H(admin), json={"plan": "starter", "days": 30}).status_code == 200
    r = requests.get(f"{API}/conversations", headers=H(member))
    assert r.status_code == 401 and "plan doesn't include your login" in r.json()["detail"]
    r = requests.post(f"{API}/auth/login", json={"email": MEM_EMAIL, "password": "member123"})
    assert r.status_code == 403 and "plan doesn't include your login" in r.json()["detail"]
    # owner unaffected
    assert requests.get(f"{API}/conversations", headers=H(shop["tok"])).status_code == 200
    # back to pro -> member works again
    requests.post(f"{API}/admin/businesses/{shop['bid']}/plan", headers=H(admin), json={"plan": "pro", "days": 30})
    assert requests.get(f"{API}/conversations", headers=H(member)).status_code == 200


def test_token_version_invalidation(shop):
    r = requests.post(f"{API}/auth/login", json={"email": OWNER_EMAIL, "password": "secret123"})
    old = r.json()["token"]
    DB.users.update_one({"id": shop["uid"]}, {"$inc": {"token_version": 1}})
    r = requests.get(f"{API}/auth/me", headers=H(old))
    assert r.status_code == 401 and "session has ended" in r.json()["detail"]
    r = requests.post(f"{API}/auth/login", json={"email": OWNER_EMAIL, "password": "secret123"})
    assert r.status_code == 200
    shop["tok"] = r.json()["token"]
    assert requests.get(f"{API}/auth/me", headers=H(shop["tok"])).status_code == 200


# --- LAST: signup rate limit (Mongo-backed)
def test_signup_rate_limit_429():
    DB.rate_hits.delete_many({})
    created, codes = [], []
    try:
        for i in range(11):
            r = requests.post(f"{API}/auth/register", json={"email": f"test_rl{i}_{STAMP}@example.com", "password": "secret123", "business_name": f"TEST_RL{i}"})
            codes.append(r.status_code)
            if r.status_code == 200:
                created.append(r.json()["user"]["business_id"])
        assert codes[:10] == [200] * 10, codes
        assert codes[10] == 429, codes
        assert DB.rate_hits.count_documents({}) >= 10
        assert DB.rate_hits.find_one({}).get("exp") is not None
    finally:
        for bid in created:
            for c in COLLS:
                DB[c].delete_many({"business_id": bid})
            DB.businesses.delete_one({"id": bid})
            DB.users.delete_many({"business_id": bid})
        DB.rate_hits.delete_many({})
