# Iteration 9: VoxCPM2 auto-connect pairing (GET/POST /api/voice/voxcpm-pair), vox_health refactor, static scripts
import os
import pytest, requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
MOCK = "https://louisiana-cancel-thickness-eddie.trycloudflare.com"
MKEY = "mockkey123"


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email}")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def H():
    return login("admin@replyflow.com", "admin123")


@pytest.fixture(scope="module")
def H2():
    return login("loadtest+706ab4fd@example.com", "loadtest123")


@pytest.fixture(scope="module", autouse=True)
def reset_settings(H):
    yield
    s = requests.get(f"{API}/settings", headers=H).json()
    s.update(voxcpm_url="", voxcpm_key="")
    requests.put(f"{API}/settings", headers=H, json=s)


def pair(H):
    r = requests.get(f"{API}/voice/voxcpm-pair", headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def post(token, **body):
    return requests.post(f"{API}/voice/voxcpm-pair/{token}", json=body)


# --- pairing token ---
def test_pair_requires_auth():
    assert requests.get(f"{API}/voice/voxcpm-pair").status_code in (401, 403)


def test_pair_shape_and_stable(H):
    a = pair(H)
    for k in ["token", "stage", "error", "gpu", "source", "url", "key", "seen_at"]:
        assert k in a
    assert isinstance(a["token"], str) and len(a["token"]) >= 20
    assert pair(H)["token"] == a["token"]


def test_pair_multitenant(H, H2):
    assert pair(H)["token"] != pair(H2)["token"]


# --- public report endpoint ---
def test_invalid_token_404():
    r = post("nope-invalid-token", stage="started")
    assert r.status_code == 404
    assert "This setup code is not valid" in r.json()["detail"]


def test_invalid_stage_422(H):
    assert post(pair(H)["token"], stage="bogus").status_code == 422


@pytest.mark.parametrize("st", ["started", "gpu", "no_gpu", "installing", "loading", "linking"])
def test_progress_stages(H, st):
    t = pair(H)["token"]
    r = post(t, stage=st)
    assert r.status_code == 200 and r.json()["ok"] is True
    assert pair(H)["stage"] == st


def test_error_stage_text(H):
    t = pair(H)["token"]
    assert post(t, stage="error", error="TEST_boom").status_code == 200
    p = pair(H)
    assert p["stage"] == "error" and p["error"] == "TEST_boom"


def test_alive_does_not_change_non_ready(H):
    t = pair(H)["token"]
    post(t, stage="installing")
    before = pair(H)["seen_at"]
    assert post(t, stage="alive").status_code == 200
    p = pair(H)
    assert p["stage"] == "installing" and p["seen_at"] == before


@pytest.mark.parametrize("u", ["https://127.0.0.1", "http://example.com", "https://169.254.169.254"])
def test_ready_private_url_blocked(H, u):
    url_before = requests.get(f"{API}/settings", headers=H).json().get("voxcpm_url")
    t = pair(H)["token"]
    r = post(t, stage="ready", url=u, key="x")
    assert r.status_code == 400
    assert r.json()["detail"].startswith("ReplyFlow could not reach the server:")
    p = pair(H)
    assert p["stage"] == "error" and "could not reach" in p["error"]
    assert requests.get(f"{API}/settings", headers=H).json().get("voxcpm_url") == url_before


def test_ready_wrong_key(H):
    t = pair(H)["token"]
    r = post(t, stage="ready", url=MOCK, key="wrong")
    assert r.status_code == 400
    assert "Wrong API key" in r.json()["detail"]


def test_ready_mock_ok_then_alive_and_mismatch(H):
    t = pair(H)["token"]
    r = post(t, stage="ready", url=MOCK + "/", key=MKEY, source="colab")
    assert r.status_code == 200, r.text
    s = requests.get(f"{API}/settings", headers=H).json()
    assert s["voxcpm_url"] == MOCK and s["voxcpm_key"] == MKEY
    p = pair(H)
    assert p["stage"] == "ready" and p["gpu"] == "Tesla T4 (mock)" and p["url"] == MOCK
    seen = p["seen_at"]
    import time; time.sleep(1.1)
    assert post(t, stage="alive").status_code == 200
    p2 = pair(H)
    assert p2["stage"] == "ready" and p2["seen_at"] > seen
    # manual url change -> waiting
    s["voxcpm_url"] = MOCK + "/x"
    assert requests.put(f"{API}/settings", headers=H, json=s).status_code == 200
    assert pair(H)["stage"] == "waiting"


# --- voxcpm-check (vox_health) ---
def test_check_private_blocked(H):
    r = requests.post(f"{API}/voice/voxcpm-check", headers=H, json={"url": "https://127.0.0.1", "key": ""})
    assert r.status_code == 200 and r.json()["ok"] is False


def test_check_mock_ok(H):
    r = requests.post(f"{API}/voice/voxcpm-check", headers=H, json={"url": MOCK, "key": MKEY})
    d = r.json()
    assert d["ok"] is True and d["gpu"] == "Tesla T4 (mock)"


# --- static scripts ---
@pytest.mark.parametrize("f", ["colab_setup.py", "modal_setup.py"])
def test_static_scripts(f):
    r = requests.get(f"{BASE_URL}/voxcpm/{f}")
    assert r.status_code == 200
    assert "def report" in r.text and "/api/voice/voxcpm-pair/" in r.text
