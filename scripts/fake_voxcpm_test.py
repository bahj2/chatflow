import asyncio, json, os, sys, threading, time
import numpy as np, uvicorn, httpx, edge_tts
sys.path.insert(0, "/app/frontend/public/voxcpm")
import voxcpm_server

CALLS = []
class Fake:
    class tts_model: sample_rate = 48000
    def generate(self, **kw):
        CALLS.append({k: (v if k not in ("reference_wav_path", "prompt_wav_path") else os.path.exists(v)) for k, v in kw.items()})
        t = np.linspace(0, 1.5, 72000); return (0.2 * np.sin(2 * np.pi * 220 * t)).astype("float32")

threading.Thread(target=lambda: uvicorn.run(voxcpm_server.create_app(Fake(), "secret123"), host="127.0.0.1", port=8099, log_level="error"), daemon=True).start()
time.sleep(2)
API = "http://localhost:8001/api"
BID = "4f0dbc25-7fad-40f4-b898-0ef8db1d9799"

async def main():
    from pymongo import MongoClient
    from dotenv import load_dotenv; load_dotenv("/app/backend/.env")
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    async with httpx.AsyncClient(timeout=120) as h:
        tok = (await h.post(f"{API}/auth/login", json={"email": "loadtest+706ab4fd@example.com", "password": "loadtest123"})).json()["token"]
        H = {"Authorization": f"Bearer {tok}"}
        print("health direct:", (await h.get("http://127.0.0.1:8099/health", headers={"Authorization": "Bearer secret123"})).json())
        print("health bad key:", (await h.get("http://127.0.0.1:8099/health")).status_code)
        sample = b"".join([c["data"] async for c in edge_tts.Communicate("សួស្តី ខ្ញុំជាម្ចាស់ហាង", "km-KH-PisethNeural").stream() if c["type"] == "audio"])
        sv = (await h.post(f"{API}/settings/seller-voice", headers=H, files={"file": ("seller.mp3", sample, "audio/mpeg")}, data={"text": ""})).json()
        print("seller voice:", sv)
        before = db.settings.find_one({"business_id": BID}, {"_id": 0, "voxcpm_url": 1, "voxcpm_key": 1})
        db.settings.update_one({"business_id": BID}, {"$set": {"voxcpm_url": "http://127.0.0.1:8099", "voxcpm_key": "secret123", "voxcpm_for": "khmer"}})
        r = (await h.post(f"{API}/voice/test", headers=H, json={"text": "សួស្តីបង! 😊 អរគុណ"})).json(); print("khmer test:", r)
        print("server got:", CALLS[-1])
        r = (await h.post(f"{API}/voice/test", headers=H, json={"text": "Hello there"})).json(); print("english test:", r["engine"], r["vox_error"])
        db.settings.update_one({"business_id": BID}, {"$set": {"voxcpm_key": "wrong"}})
        r = (await h.post(f"{API}/voice/test", headers=H, json={"text": "សួស្តីបង"})).json(); print("wrong key:", r["engine"], "|", r["vox_error"])
        db.settings.update_one({"business_id": BID}, {"$set": {"voxcpm_url": "http://127.0.0.1:8098", "voxcpm_key": "secret123"}})
        r = (await h.post(f"{API}/voice/test", headers=H, json={"text": "សួស្តីបង"})).json(); print("server down:", r["engine"], "|", r["vox_error"])
        print("check http:", (await h.post(f"{API}/voice/voxcpm-check", headers=H, json={"url": "http://x.com"})).json())
        print("check bad host:", (await h.post(f"{API}/voice/voxcpm-check", headers=H, json={"url": "https://nonexistent-voxcpm-test.trycloudflare.com"})).json())
        # real incoming Khmer voice message through the whole pipeline
        db.settings.update_one({"business_id": BID}, {"$set": {"voxcpm_url": "http://127.0.0.1:8099", "voxcpm_key": "secret123"}})
        q = b"".join([c["data"] async for c in edge_tts.Communicate("សួស្តីបង តើហាងបើកម៉ោងប៉ុន្មាន?", "km-KH-SreymomNeural").stream() if c["type"] == "audio"])
        r = (await h.post(f"{API}/public/{BID}/voice", data={"session_id": "vox-e2e-1", "name": "Vox test"}, files={"file": ("q.mp3", q, "audio/mpeg")}, headers={"X-Forwarded-For": "10.5.5.5"})).json()
        print("incoming voice -> engine:", [a.get("engine") for a in r["reply"]["attachments"] if a["type"] == "audio"], "| reply:", r["reply"]["text"][:80])
        db.settings.update_one({"business_id": BID}, {"$set": {"voxcpm_url": before.get("voxcpm_url", ""), "voxcpm_key": before.get("voxcpm_key", "")}})

asyncio.run(main())
