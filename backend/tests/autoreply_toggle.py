# helper: python autoreply_toggle.py true|false  -> sets admin auto_reply
import os, sys, requests
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
t = requests.post(f"{API}/auth/login", json={"email": "admin@replyflow.com", "password": "admin123"}).json()["token"]
h = {"Authorization": f"Bearer {t}"}
s = requests.get(f"{API}/settings", headers=h).json()
s["auto_reply"] = sys.argv[1] == "true"
r = requests.put(f"{API}/settings", headers=h, json=s)
print(r.status_code, requests.get(f"{API}/settings", headers=h).json()["auto_reply"])
