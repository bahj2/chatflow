# Seed shop for iter29 UI test: products with categories and stock states
import os, json, uuid, requests
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
email = f"test_iter29_ui_{uuid.uuid4().hex[:6]}@example.com"
r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!", "business_name": "TEST_iter29 UI"}).json()
tok = r.get("token") or requests.post(f"{API}/auth/login", json={"email": email, "password": "Passw0rd!"}).json()["token"]
h = {"Authorization": f"Bearer {tok}"}
ids = {}
for name, cat, stock in [("TEST_Sneaker", "Shoes", 10), ("TEST_Sandal", "Shoes", 2), ("TEST_Bag", "Bags", 0), ("TEST_Hat", "", None)]:
    ids[name] = requests.post(f"{API}/products", json={"name": name, "price": "$10", "category": cat, "stock": stock}, headers=h).json()["id"]
print(json.dumps({"email": email, "ids": ids}))
