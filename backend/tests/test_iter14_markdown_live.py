# Iteration 14: live LLM replies to general product questions contain no markdown / [[show tags (loadtest business, 6 products)
import os
import uuid

import pytest
import requests

import test_iter13_catalog_priority as T

ITEMS = [("Gemini Pro", "10$", "1 month AI account, no warranty", "blue"),
         ("Canva Pro", "5$", "1 month design tool account for graphic design", "purple"),
         ("ChatGPT Plus", "15$", "1 month AI chat account", "green"),
         ("Netflix Premium", "7$", "1 month 4K streaming profile", None),
         ("Spotify Premium", "4$", "1 month music account", None),
         ("CapCut Pro", "6$", "1 month video editing account", "red")]


@pytest.fixture(scope="module")
def ctx():
    r = requests.post(f"{T.API}/auth/login", json={"email": T.EMAIL, "password": T.PW})
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    c = {"h": h, "bid": r.json()["user"]["business_id"]}
    for p in requests.get(f"{T.API}/products", headers=h).json():
        requests.delete(f"{T.API}/products/{p['id']}", headers=h)
    c["ids"] = {T.mk(c, *i)["id"] for i in ITEMS}
    yield c
    if not os.environ.get("KEEP_PRODUCTS"):
        for pid in c["ids"]:
            requests.delete(f"{T.API}/products/{pid}", headers=h)


def clean(t):
    return "**" not in t and "[[show" not in t and "__" not in t and not any(l.lstrip().startswith(("# ", "* ", "- ")) for l in t.split("\n"))


@pytest.mark.parametrize("q", ["What do you sell?", "បងលក់អ្វីខ្លះ?", "Can you list all your products with prices?"])
def test_general_no_markdown(ctx, q):
    r = T.chat(ctx, f"TEST_md_{uuid.uuid4().hex[:6]}", q)
    got = {a["product_id"] for a in r["attachments"] if a["type"] == "product"}
    print(q, "->", repr(r["text"]), len(got & ctx["ids"]))
    assert clean(r["text"]), r["text"]
    assert len(got & ctx["ids"]) >= 5


def test_ai_test_no_markdown(ctx):
    a = requests.post(f"{T.API}/ai/test", headers=ctx["h"], json={"text": "list everything you sell"}, timeout=120)
    assert a.status_code == 200
    print("ai/test ->", repr(a.json()["reply"]))
    assert clean(a.json()["reply"])
    assert len({x["product_id"] for x in a.json()["products"]} & ctx["ids"]) >= 5
