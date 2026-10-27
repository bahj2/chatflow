# Iteration 31: Forgot password (6-digit code by email) API tests
import hashlib
import hmac
import os
import time
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


def _env(path, key):
    for line in open(path):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


JWT_SECRET = _env("/app/backend/.env", "JWT_SECRET")
MONGO_URL = _env("/app/backend/.env", "MONGO_URL")
DB_NAME = _env("/app/backend/.env", "DB_NAME")
db = MongoClient(MONGO_URL)[DB_NAME]
CODE = "424242"


def digest(email, code):
    return hmac.new(JWT_SECRET.encode(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def clear_limits():
    db.rate_hits.delete_many({"k": {"$regex": "^pwreset"}})


def set_code(email, code=CODE):
    r = db.password_resets.update_one({"email": email}, {"$set": {"digest": digest(email, code)}})
    assert r.matched_count == 1


def forgot(email):
    clear_limits()
    return requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": email})


created = []


def make_user():
    email = f"test_pwreset_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "OldPass123", "business_name": "TEST_PwReset"})
    assert r.status_code == 200, r.text
    created.append(email)
    return email, r.json()["token"]


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for e in created:
        u = db.users.find_one({"email": e})
        if u:
            db.businesses.delete_many({"id": u.get("business_id")})
            db.users.delete_one({"email": e})
        db.password_resets.delete_many({"email": e})
    clear_limits()


# --- forgot-password ---
def test_forgot_ok_and_record_created():
    email, _ = make_user()
    r = forgot(email)
    assert r.status_code == 200 and r.json() == {"ok": True}
    rec = db.password_resets.find_one({"email": email})
    assert rec and rec["tries"] == 0 and len(rec["digest"]) == 64


def test_forgot_unknown_email_same_response():
    r = forgot(f"nobody_{uuid.uuid4().hex[:6]}@example.com")
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_forgot_rate_limit_60s():
    email, _ = make_user()
    assert forgot(email).status_code == 200
    r2 = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": email})
    assert r2.status_code == 429
    assert "wait a minute" in r2.json()["detail"].lower()


def test_forgot_invalid_email_400():
    clear_limits()
    r = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": "not-an-email"})
    assert r.status_code == 400


def test_forgot_superadmin_no_record():
    db.password_resets.delete_many({"email": "admin@replyflow.com"})
    r = forgot("admin@replyflow.com")
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert db.password_resets.find_one({"email": "admin@replyflow.com"}) is None


# --- reset-password ---
def test_wrong_code_400_and_lockout_after_5():
    email, _ = make_user()
    forgot(email)
    set_code(email)
    for i in range(5):
        r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"email": email, "code": "111111", "password": "NewPass456"})
        assert r.status_code == 400, r.text
    r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"email": email, "code": CODE, "password": "NewPass456"})
    assert r.status_code == 400 and "Too many wrong codes" in r.json()["detail"]
    assert db.password_resets.find_one({"email": email}) is None
    r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"email": email, "code": CODE, "password": "NewPass456"})
    assert r.status_code == 400


def test_weak_password_422():
    email, _ = make_user()
    forgot(email)
    set_code(email)
    for pw in ["Ab1", "abcdefghij", "1234567890"]:
        r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"email": email, "code": CODE, "password": pw})
        assert r.status_code == 422, (pw, r.status_code)
    # weak attempts must not consume tries
    assert db.password_resets.find_one({"email": email})["tries"] == 0


def test_full_reset_flow():
    email, old_token = make_user()
    assert requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 200
    forgot(email)
    set_code(email)
    r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"email": email.upper(), "code": CODE, "password": "NewPass456"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["token"] and data["user"]["email"] == email
    assert "password_hash" not in data["user"]
    u = db.users.find_one({"email": email})
    assert u["password_hash"].startswith("$2b$") and u["email_verified"] is True
    # single use
    r2 = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"email": email, "code": CODE, "password": "Another789"})
    assert r2.status_code == 400
    # old session revoked, new works
    assert requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401
    assert requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {data['token']}"}).status_code == 200
    # old password fails, new works
    assert requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "OldPass123"}).status_code == 401
    r3 = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "NewPass456"})
    assert r3.status_code == 200 and r3.json()["token"]


def test_expired_code_400():
    from datetime import datetime, timezone, timedelta
    email, _ = make_user()
    forgot(email)
    set_code(email)
    db.password_resets.update_one({"email": email}, {"$set": {"exp": datetime.now(timezone.utc) - timedelta(minutes=1)}})
    r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"email": email, "code": CODE, "password": "NewPass456"})
    assert r.status_code == 400


def test_new_request_replaces_old_code():
    email, _ = make_user()
    forgot(email)
    set_code(email, "111222")
    forgot(email)
    assert db.password_resets.count_documents({"email": email}) == 1
    r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"email": email, "code": "111222", "password": "NewPass456"})
    assert r.status_code == 400


def test_reset_clears_login_lockout():
    email, _ = make_user()
    for _ in range(6):
        requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "Wrong0000"})
    locked = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "OldPass123"})
    print("after 6 fails login status:", locked.status_code, locked.text[:120])
    forgot(email)
    set_code(email)
    r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"email": email, "code": CODE, "password": "NewPass456"})
    assert r.status_code == 200
    r2 = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "NewPass456"})
    assert r2.status_code == 200, r2.text
