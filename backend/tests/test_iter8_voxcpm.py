# Iter8: VoxCPM2 setup scripts, voxcpm-check, settings https rule, voice test fallback
import os, py_compile, tempfile
import pytest, requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
EMAIL, PW = "loadtest+706ab4fd@example.com", "loadtest123"


@pytest.fixture(scope="module")
def H():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": PW})
    if r.status_code != 200:
        pytest.skip("login failed")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def orig(H):
    s = requests.get(f"{API}/settings", headers=H).json()
    yield s
    s2 = requests.get(f"{API}/settings", headers=H).json()
    s2.update(voxcpm_url="", voxcpm_key="")
    assert requests.put(f"{API}/settings", headers=H, json=s2).status_code == 200


# Static scripts served by frontend
@pytest.mark.parametrize("f", ["voxcpm_server.py", "colab_setup.py", "modal_voxcpm.py", "modal_setup.py"])
def test_scripts_served_and_compile(f):
    r = requests.get(f"{BASE_URL}/voxcpm/{f}")
    assert r.status_code == 200
    assert "<html" not in r.text.lower()[:200]
    p = os.path.join(tempfile.mkdtemp(), f)
    open(p, "w").write(r.text)
    py_compile.compile(p, doraise=True)


# voxcpm-check
def test_check_requires_auth():
    assert requests.post(f"{API}/voice/voxcpm-check", json={"url": "https://x.com"}).status_code == 401


def test_check_http_rejected(H):
    d = requests.post(f"{API}/voice/voxcpm-check", headers=H, json={"url": "http://x.com"}).json()
    assert d["ok"] is False and "https://" in d["error"]


def test_check_unreachable(H):
    d = requests.post(f"{API}/voice/voxcpm-check", headers=H, json={"url": "https://nonexistent-voxcpm-zz.trycloudflare.com", "key": "k"}, timeout=60).json()
    assert d["ok"] is False and "Cannot reach" in d["error"]


# PUT settings https rule
def test_settings_http_400(H, orig):
    s = dict(orig, voxcpm_url="http://x")
    assert requests.put(f"{API}/settings", headers=H, json=s).status_code == 400


def test_settings_strip_slash(H, orig):
    s = dict(orig, voxcpm_url="https://abc.modal.run/", voxcpm_key="k1")
    r = requests.put(f"{API}/settings", headers=H, json=s)
    assert r.status_code == 200 and r.json()["voxcpm_url"] == "https://abc.modal.run"
    assert requests.get(f"{API}/settings", headers=H).json()["voxcpm_url"] == "https://abc.modal.run"


def test_voice_test_bogus_vox_fallback(H, orig):
    s = dict(orig, voxcpm_url="https://nonexistent-voxcpm-zz.trycloudflare.com", voxcpm_key="k", voxcpm_for="khmer")
    assert requests.put(f"{API}/settings", headers=H, json=s).status_code == 200
    d = requests.post(f"{API}/voice/test", headers=H, json={"text": "សួស្តីបង"}, timeout=120).json()
    assert d["engine"] == "microsoft" and "Cannot reach" in (d["vox_error"] or "")


def test_settings_empty_and_khmer_regression(H, orig):
    s = dict(orig, voxcpm_url="", voxcpm_key="")
    r = requests.put(f"{API}/settings", headers=H, json=s)
    assert r.status_code == 200 and r.json()["voxcpm_url"] == ""
    d = requests.post(f"{API}/voice/test", headers=H, json={"text": "សួស្តីបង"}, timeout=120).json()
    assert d["engine"] == "microsoft" and d["vox_error"] is None
    assert requests.get(f"{API}/media/{d['media_id']}", headers=H).status_code in (200, 401, 403)
