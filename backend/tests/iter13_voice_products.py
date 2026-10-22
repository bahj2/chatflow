# Iteration 13: Khmer voice message asking about products -> reply has product attachments, no [[show in spoken text
import os
import time
import uuid

import requests

API = "https://chatflow-pilot.preview.emergentagent.com/api"
r = requests.post(f"{API}/auth/login", json={"email": "loadtest+706ab4fd@example.com", "password": "loadtest123"}).json()
h, bid = {"Authorization": "Bearer " + r["token"]}, r["user"]["business_id"]
clip = "/tmp/km_ask_products.mp3"
if not os.path.exists(clip):
    for i in range(3):
        v = requests.post(f"{API}/voice/test", headers=h, json={"text": "បងលក់អ្វីខ្លះ?"}, timeout=70)
        print("voice/test", v.status_code, v.text[:150])
        if v.status_code == 200:
            open(clip, "wb").write(requests.get(f"{API}/media/{v.json()['media_id']}").content)
            break
        time.sleep(10)
src = clip if os.path.exists(clip) else "/tmp/vox_km.mp3"
print("using clip", src, os.path.exists(src))
sid = f"TEST_voice_{uuid.uuid4().hex[:8]}"
v = requests.post(f"{API}/public/{bid}/voice", data={"session_id": sid}, files={"file": ("a.mp3", open(src, "rb"), "audio/mpeg")}, timeout=30)
print("voice post", v.status_code, v.text)
t0 = time.time()
while time.time() - t0 < 200:
    msgs = requests.get(f"{API}/public/{bid}/chat/{sid}").json()["messages"]
    ai = [m for m in msgs if m["role"] == "ai"]
    if ai:
        u = [m for m in msgs if m["role"] == "user"][0]
        print("user transcript:", u["text"], [a["type"] for a in u["attachments"]])
        m = ai[0]
        print("AI text:", m["text"])
        print("attachments:", [(a["type"], a.get("name"), a.get("engine"), bool(a.get("media_id"))) for a in m["attachments"]])
        print("has [[show:", "[[show" in m["text"])
        print("elapsed", round(time.time() - t0))
        break
    time.sleep(5)
else:
    print("TIMEOUT no AI reply")
