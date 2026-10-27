# Iter29: product category + stock tracking, stock PATCH, settle_order stock decrement, catalog/order_problem units, AI sold-out
import os, sys, uuid, asyncio, pytest, requests
from datetime import datetime, timezone

sys.path.insert(0, "/app/backend")
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api"


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


def register(tag):
    email = f"test_iter29_{tag}_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!", "business_name": f"TEST_iter29 {tag}"}, timeout=30)
    assert r.status_code in (200, 201), r.text
    d = r.json()
    if not d.get("token"):
        d = requests.post(f"{API}/auth/login", json={"email": email, "password": "Passw0rd!"}, timeout=30).json()
    return {"email": email, "token": d["token"], "business_id": d["user"]["business_id"]}


@pytest.fixture(scope="module")
def shop():
    return register("a")


@pytest.fixture(scope="module")
def other():
    return register("b")


def mk(shop, **kw):
    body = {"name": "TEST_prod", "price": "$5", "description": "d", **kw}
    return requests.post(f"{API}/products", json=body, headers=hdr(shop["token"]), timeout=30)


# Product create/update with category + stock
def test_create_with_category_stock(shop):
    r = mk(shop, name="TEST_Shirt", category="Clothes", stock=5)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["category"] == "Clothes" and d["stock"] == 5
    lst = requests.get(f"{API}/products", headers=hdr(shop["token"]), timeout=30).json()
    got = next(p for p in lst if p["id"] == d["id"])
    assert got["stock"] == 5 and got["category"] == "Clothes" and "_id" not in got


def test_create_untracked_default_null(shop):
    r = mk(shop, name="TEST_Untracked")
    assert r.status_code == 200
    assert r.json()["stock"] is None and r.json()["category"] == ""


def test_negative_stock_422(shop):
    assert mk(shop, stock=-1).status_code == 422


def test_category_too_long_422(shop):
    assert mk(shop, category="x" * 41).status_code == 422


def test_update_category_stock(shop):
    pid = mk(shop, name="TEST_Upd", stock=2).json()["id"]
    r = requests.put(f"{API}/products/{pid}", json={"name": "TEST_Upd2", "price": "$6", "category": "Bags", "stock": 9}, headers=hdr(shop["token"]), timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["stock"] == 9 and r.json()["category"] == "Bags"
    r = requests.put(f"{API}/products/{pid}", json={"name": "TEST_Upd2", "stock": -3}, headers=hdr(shop["token"]), timeout=30)
    assert r.status_code == 422


# PATCH stock
def test_patch_stock(shop, other):
    pid = mk(shop, name="TEST_Patch", stock=1).json()["id"]
    r = requests.patch(f"{API}/products/{pid}/stock", json={"stock": 7}, headers=hdr(shop["token"]), timeout=30)
    assert r.status_code == 200 and r.json()["stock"] == 7
    r = requests.patch(f"{API}/products/{pid}/stock", json={"stock": None}, headers=hdr(shop["token"]), timeout=30)
    assert r.status_code == 200 and r.json()["stock"] is None
    assert requests.patch(f"{API}/products/{pid}/stock", json={"stock": -1}, headers=hdr(shop["token"]), timeout=30).status_code == 422
    r = requests.patch(f"{API}/products/{pid}/stock", json={"stock": 3}, headers=hdr(other["token"]), timeout=30)
    assert r.status_code == 404
    r = requests.patch(f"{API}/products/nonexistent/stock", json={"stock": 3}, headers=hdr(shop["token"]), timeout=30)
    assert r.status_code == 404
    lst = requests.get(f"{API}/products", headers=hdr(shop["token"]), timeout=30).json()
    assert next(p for p in lst if p["id"] == pid)["stock"] is None


# settle_order via mark-paid decrements stock
def _insert_order(bid, items):
    from motor.motor_asyncio import AsyncIOMotorClient
    oid = str(uuid.uuid4())

    async def go():
        c = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        await c["replyflow"].orders.insert_one({"id": oid, "business_id": bid, "conversation_id": "TEST_noconv_" + oid, "channel": "telegram",
                                                "customer": "TEST", "number": "RF-TEST29", "items": items, "total": 1, "currency": "USD",
                                                "mode": "relay", "status": "pending", "created_at": datetime.now(timezone.utc).isoformat()})
        c.close()
    asyncio.run(go())
    return oid


def test_mark_paid_decrements_stock(shop):
    a = mk(shop, name="TEST_A", stock=5).json()["id"]
    b = mk(shop, name="TEST_B", stock=1).json()["id"]
    u = mk(shop, name="TEST_U").json()["id"]
    oid = _insert_order(shop["business_id"], [{"product_id": a, "name": "A", "qty": 2}, {"product_id": b, "name": "B", "qty": 3},
                                              {"product_id": u, "name": "U", "qty": 4}])
    r = requests.post(f"{API}/orders/{oid}/mark-paid", headers=hdr(shop["token"]), timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paid"
    lst = {p["id"]: p for p in requests.get(f"{API}/products", headers=hdr(shop["token"]), timeout=30).json()}
    assert lst[a]["stock"] == 3
    assert lst[b]["stock"] == 0
    assert lst[u]["stock"] is None
    # second mark-paid -> 409, no double decrement
    assert requests.post(f"{API}/orders/{oid}/mark-paid", headers=hdr(shop["token"]), timeout=30).status_code == 409
    lst = {p["id"]: p for p in requests.get(f"{API}/products", headers=hdr(shop["token"]), timeout=30).json()}
    assert lst[a]["stock"] == 3


# Unit: catalog_text + order_problem
def test_catalog_text_stock():
    from ai import catalog_text
    t = catalog_text([{"id": "aaaaaaaa1", "name": "X", "price": "$1", "category": "Cat1", "stock": 0},
                      {"id": "bbbbbbbb1", "name": "Y", "price": "$1", "stock": 4},
                      {"id": "cccccccc1", "name": "Z", "price": "$1", "stock": None}])
    assert "Cat1" in t and "SOLD OUT" in t and "4 left" in t and "in stock" in t


def test_order_problem_stock():
    from orders import order_problem
    assert "sold out" in order_problem([({"name": "X", "price": "$1", "stock": 0}, 1)])
    assert "only 2" in order_problem([({"name": "X", "price": "$1", "stock": 2}, 3)])
    assert order_problem([({"name": "X", "price": "$1", "stock": 2}, 2)]) == ""
    assert order_problem([({"name": "X", "price": "$1", "stock": None}, 99)]) == ""


# LLM: sold-out product
def test_ai_says_sold_out(shop):
    mk(shop, name="TEST_Red Dragon Jacket", price="$25", category="Jackets", stock=0)
    r = requests.post(f"{API}/ai/test", json={"text": "Do you have the Red Dragon Jacket? I want to buy one."}, headers=hdr(shop["token"]), timeout=90)
    assert r.status_code == 200, r.text
    reply = r.json()["reply"].lower()
    print("AI reply:", reply)
    assert "sold out" in reply or "out of stock" in reply or "not available" in reply or "unavailable" in reply
