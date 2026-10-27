# Iter28: Facebook lock for shop owners + billing checkout relay mode (KHQR.dev)
import os, uuid, pytest, requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api"


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_tok():
    return login("admin@replyflow.com", "admin123")["token"]


@pytest.fixture(scope="module")
def shop():
    email = f"test_iter28_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!", "business_name": "TEST_iter28 Shop"}, timeout=30)
    assert r.status_code in (200, 201), r.text
    d = r.json()
    tok = d.get("token") or login(email, "Passw0rd!")["token"]
    return {"email": email, "token": tok}


# Meta status lock
def test_meta_status_superadmin_unlocked(admin_tok):
    r = requests.get(f"{API}/meta/status", headers=hdr(admin_tok), timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["locked"] is False


def test_meta_status_shop_locked(shop):
    r = requests.get(f"{API}/meta/status", headers=hdr(shop["token"]), timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["locked"] is True


@pytest.mark.parametrize("path", ["/meta/facebook/start", "/meta/facebook/quick"])
def test_fb_start_quick_403_for_shop(shop, path):
    r = requests.post(f"{API}{path}", headers=hdr(shop["token"]), json={"base_url": BASE_URL, "return_url": BASE_URL}, timeout=30)
    assert r.status_code == 403, r.text
    assert r.json().get("detail") == "Facebook Messenger is coming soon."


def test_fb_login_available_false():
    r = requests.get(f"{API}/auth/facebook/available", timeout=30)
    assert r.status_code == 200
    assert r.json()["available"] is False


def test_fb_login_start_503():
    r = requests.post(f"{API}/auth/facebook/start", json={"base_url": BASE_URL, "return_url": BASE_URL}, timeout=30)
    assert r.status_code == 503, r.text


# Billing checkout (single KHQR.dev call)
def test_checkout_pro_relay_khr(shop):
    r = requests.post(f"{API}/billing/checkout", headers=hdr(shop["token"]), json={"item": "pro"}, timeout=90)
    print(r.status_code, r.text[:800])
    assert r.status_code == 200, r.text
    d = r.json()
    inv = d.get("invoice", d)
    assert inv.get("mode") == "relay", inv
    assert inv.get("currency") == "KHR", inv
    assert float(inv.get("price_usd")) == 25
