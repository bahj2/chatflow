# Iteration 3: Google auth endpoint + password login regression + allowed_emails settings persistence
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
ADMIN = {"email": "admin@replyflow.com", "password": "admin123"}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


# Google auth
class TestGoogleAuth:
    def test_bogus_session_401(self):
        r = requests.post(f"{BASE_URL}/api/auth/google", json={"session_id": "bogus"})
        assert r.status_code == 401
        assert r.json()["detail"] == "Google sign-in failed. Please try again."

    def test_empty_session_401(self):
        r = requests.post(f"{BASE_URL}/api/auth/google", json={"session_id": ""})
        assert r.status_code in (400, 401, 422)

    def test_missing_body_422(self):
        r = requests.post(f"{BASE_URL}/api/auth/google", json={})
        assert r.status_code == 422


# Password login regression
class TestPasswordLogin:
    def test_login_and_me(self, token, h):
        assert isinstance(token, str) and token
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=h)
        assert r.status_code == 200
        d = r.json()
        assert d["email"] == ADMIN["email"]
        assert "password_hash" not in d and "_id" not in d

    def test_wrong_password_401(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "TEST_nobody@x.com", "password": "bad"})
        assert r.status_code == 401

    def test_me_without_token_401(self):
        assert requests.get(f"{BASE_URL}/api/auth/me").status_code == 401


# allowed_emails in settings
class TestAllowedEmails:
    def test_put_allowed_emails_persists_and_cleanup(self, h):
        orig = requests.get(f"{BASE_URL}/api/settings", headers=h).json()
        assert "allowed_emails" in orig
        body = dict(orig)
        body["allowed_emails"] = ["test_user@gmail.com"]
        try:
            r = requests.put(f"{BASE_URL}/api/settings", json=body, headers=h)
            assert r.status_code == 200
            g = requests.get(f"{BASE_URL}/api/settings", headers=h).json()
            assert g["allowed_emails"] == ["test_user@gmail.com"]
            # other fields unchanged
            assert g["business_name"] == orig["business_name"]
            assert g["quick_replies"] == orig["quick_replies"]
        finally:
            requests.put(f"{BASE_URL}/api/settings", json=orig, headers=h)
        g = requests.get(f"{BASE_URL}/api/settings", headers=h).json()
        assert g["allowed_emails"] == orig["allowed_emails"]

    def test_put_without_allowed_emails_defaults(self, h):
        """Older clients omitting allowed_emails -> field resets to [] (model default)."""
        orig = requests.get(f"{BASE_URL}/api/settings", headers=h).json()
        body = {k: v for k, v in orig.items() if k != "allowed_emails"}
        r = requests.put(f"{BASE_URL}/api/settings", json=body, headers=h)
        assert r.status_code == 200
        requests.put(f"{BASE_URL}/api/settings", json=orig, headers=h)

    def test_settings_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/settings").status_code == 401
