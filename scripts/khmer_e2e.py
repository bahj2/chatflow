import asyncio, os, sys, time, difflib, httpx
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient
import media as M
db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
API = "http://localhost:8001/api"
TEST_BID = "4f0dbc25-7fad-40f4-b898-0ef8db1d9799"
ADMIN_BID = "da4f34c0-2f00-41e1-ab8c-86332eada73f"

async def main():
    msgs = [m async for m in db.messages.find({"business_id": ADMIN_BID, "role": "user", "attachments.type": "audio"})]
    async with httpx.AsyncClient(timeout=120) as h:
        for i, m in enumerate(msgs):
            mp3, _ = await M.load_media(db, m["attachments"][0]["media_id"])
            t0 = time.perf_counter()
            r = (await h.post(f"{API}/public/{TEST_BID}/voice", data={"session_id": f"khmer-e2e2-{i}", "name": "Khmer test"},
                              files={"file": ("v.mp3", mp3, "audio/mpeg")}, headers={"X-Forwarded-For": f"10.6.7.{i}"})).json()
            took = time.perf_counter() - t0
            hist = (await h.get(f"{API}/public/{TEST_BID}/chat/khmer-e2e2-{i}")).json()["messages"]
            reply = r["reply"]
            audio_att = [a for a in reply["attachments"] if a["type"] == "audio"][0]
            voice, _ = await M.load_media(db, audio_att["media_id"])
            heard = await M.transcribe(voice)
            norm = lambda t: "".join(c for c in t if "\u1780" <= c <= "\u17ff")
            print(f"--- message {i+1}  ({took:.1f}s total)")
            print("customer said (now understood):", hist[0]["text"])
            print("AI replied:", reply["text"])
            print("voice engine:", audio_att["engine"], "| clarity:", round(difflib.SequenceMatcher(None, norm(reply["text"]), norm(heard)).ratio() * 100, 1), "%")
            # fix the old wrong transcript in the real chat history
            await db.messages.update_one({"id": m["id"]}, {"$set": {"text": hist[0]["text"]}})

asyncio.run(main())
