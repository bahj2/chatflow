# Iteration 13: product catalog overrides chat history, general vs specific product questions, ai/test products
import io
import os
import re
import time
import uuid

import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
API = BASE_URL + "/api"
EMAIL, PW = "loadtest+706ab4fd@example.com", "loadtest123"
TEAM = re.compile(r"team (member )?(will|is going to|can) (contact|follow|reach|get back)|follow up with you|get back to you", re.I)
CREATED = []
RESULTS = {}


def png(color):
    b = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(b, "PNG")
    return b.getvalue()


@pytest.fixture(scope="module")
def ctx():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": PW})
    assert r.status_code == 200
    tok = r.json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    bid = r.json()["user"]["business_id"]
    s = requests.get(f"{API}/settings", headers=h).json()
    assert s["auto_reply"] and s["voice_replies"]
    # ensure no leftover products
    for p in requests.get(f"{API}/products", headers=h).json():
        requests.delete(f"{API}/products/{p['id']}", headers=h)
    yield {"h": h, "bid": bid}
    for pid in ([] if os.environ.get("KEEP_PRODUCTS") else CREATED):
        requests.delete(f"{API}/products/{pid}", headers=h)
    print("RESULTS", RESULTS)


def mk(ctx, name, price, desc, color=None):
    mid = ""
    if color:
        r = requests.post(f"{API}/media/image", headers=ctx["h"], files={"file": ("p.png", png(color), "image/png")})
        assert r.status_code == 200, r.text
        mid = r.json()["id"]
    r = requests.post(f"{API}/products", headers=ctx["h"], json={"name": name, "price": price, "description": desc, "image_media_id": mid})
    assert r.status_code == 200, r.text
    CREATED.append(r.json()["id"])
    return r.json()


def chat(ctx, sid, text):
    for _ in range(3):
        r = requests.post(f"{API}/public/{ctx['bid']}/chat", json={"session_id": sid, "text": text}, timeout=120)
        if r.status_code != 429:
            break
        time.sleep(20)
    assert r.status_code == 200, r.text
    return r.json()["reply"]


# history bias reproduction: no products -> ask -> add product -> ask again in same session (3 runs)
def test_history_bias_catalog_wins(ctx):
    passes, details = 0, []
    for run in range(3):
        sid = f"TEST_bias_{uuid.uuid4().hex[:8]}"
        before = chat(ctx, sid, "What do you sell? Do you sell any digital accounts?")
        details.append(("before", before["text"][:200]))
        p = mk(ctx, "Gemini Pro", "10$", "1 month account, no warranty", "blue")
        after = chat(ctx, sid, "I saw you sell something, what is it?")
        t = after["text"]
        pats = [a for a in after["attachments"] if a["type"] == "product"]
        ok = ("gemini" in t.lower() and "10" in t and not TEAM.search(t) and "[[show" not in t
              and any(a["product_id"] == p["id"] and a["media_id"] == p["image_media_id"] for a in pats))
        passes += ok
        details.append(("after", ok, t[:300], [a["name"] for a in pats]))
        requests.delete(f"{API}/products/{p['id']}", headers=ctx["h"])
    RESULTS["bias"] = (passes, details)
    print(details)
    assert passes == 3, details


# general question -> all products; specific -> 1-3
def test_general_and_specific(ctx):
    items = [("Gemini Pro", "10$", "1 month AI account, no warranty", "blue"),
             ("Canva Pro", "5$", "1 month design tool account for graphic design", "purple"),
             ("ChatGPT Plus", "15$", "1 month AI chat account", "green"),
             ("Netflix Premium", "7$", "1 month 4K streaming profile", None),
             ("Spotify Premium", "4$", "1 month music account", None),
             ("CapCut Pro", "6$", "1 month video editing account", "red")]
    ps = [mk(ctx, *i) for i in items]
    ids = {p["id"] for p in ps}
    out = {}
    for label, q in [("km", "បងលក់អ្វីខ្លះ?"), ("en", "What do you sell?")]:
        r = chat(ctx, f"TEST_gen_{label}_{uuid.uuid4().hex[:6]}", q)
        got = {a["product_id"] for a in r["attachments"] if a["type"] == "product"}
        out[label] = (len(got & ids), r["text"][:300])
    r = chat(ctx, f"TEST_spec_{uuid.uuid4().hex[:6]}", "anything for design under 6 dollars?")
    spec = [a["name"] for a in r["attachments"] if a["type"] == "product"]
    out["spec"] = (spec, r["text"][:300])
    # ai/test
    a = requests.post(f"{API}/ai/test", headers=ctx["h"], json={"text": "what do you sell?"}, timeout=120)
    assert a.status_code == 200
    out["ai_test"] = (len({x["product_id"] for x in a.json()["products"]} & ids), a.json()["reply"][:300])
    RESULTS["general"] = out
    print(out)
    assert out["km"][0] == 6 and out["en"][0] == 6, out
    assert 1 <= len(spec) <= 3 and "Canva Pro" in spec, out
    assert out["ai_test"][0] == 6, out
    RESULTS["product_ids"] = list(ids)
