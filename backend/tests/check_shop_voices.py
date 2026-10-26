"""Check: 3 shops (bot 1-3) each speak as a different person — own seller name, greeting and VoxCPM2 cloned voice."""
import asyncio
import io
import os
import sys
import time
import wave

import httpx
import numpy as np

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
import media as M  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from server import tg_secret  # noqa: E402

API = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0] + "/api"
SAMPLE = "សួស្តីបង ខ្ញុំជាម្ចាស់ហាង។ ហាងយើងមានទំនិញល្អៗ តម្លៃសមរម្យ ហើយដឹកជញ្ជូនដល់ផ្ទះរហ័ស។ សូមអរគុណដែលគាំទ្រ។"
TEST = "អរគុណបង! អាវនេះមានទំហំ M និង L តម្លៃប្រាំបីដុល្លារ។"
SHOPS = [
    ("Bot 1 Shop", "Dara", "A deep-voiced middle-aged man, calm and warm", "សួស្តីបង! ខ្ញុំឈ្មោះដារ៉ា ពីហាងទី១។"),
    ("Bot 2 Shop", "Sreymom", "A bright, cheerful young woman, speaking fast", "សួស្តីបង! ខ្ញុំឈ្មោះស្រីមុំ ពីហាងទី២។"),
    ("Bot 3 Shop", "Yay Kim", "A gentle elderly woman, slow and kind", "សួស្តីកូន! យាយឈ្មោះគីម ពីហាងទី៣។"),
]


def pitch(mp3_wav16k: bytes) -> float:
    with wave.open(io.BytesIO(mp3_wav16k)) as w:
        sr, x = w.getframerate(), np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)
    f0 = []
    for i in range(0, len(x) - 1024, 512):
        fr = x[i:i + 1024] - x[i:i + 1024].mean()
        if np.sqrt((fr ** 2).mean()) < 500:
            continue
        ac = np.correlate(fr, fr, "full")[1023:]
        lo, hi = sr // 400, sr // 70
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[lag] > 0.3 * ac[0]:
            f0.append(sr / lag)
    return float(np.median(f0)) if f0 else 0.0


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    stamp = str(int(time.time()))[-6:]
    async with httpx.AsyncClient(timeout=120) as h:
        for i, (shop, who, design, greet) in enumerate(SHOPS, 1):
            sample = await M.hf_voxcpm(SAMPLE, timeout=120, voice=design)
            wav = await M.to_wav16k(sample)
            r = await h.post(f"{API}/auth/register", json={"email": f"shop{i}-{stamp}@example.com", "password": "shoptest123", "business_name": shop})
            tok, bid = r.json()["token"], r.json()["user"]["business_id"]
            H = {"Authorization": f"Bearer {tok}"}
            up = await h.post(f"{API}/settings/seller-voice", headers=H, files={"file": ("s.mp3", sample, "audio/mpeg")})
            cur = (await h.get(f"{API}/settings", headers=H)).json()
            cur.update(assistant_name=who, greeting=greet)
            assert (await h.put(f"{API}/settings", headers=H, json=cur)).status_code == 200
            out = await h.post(f"{API}/voice/test", headers=H, json={"text": TEST})
            res = out.json()
            clone = (await h.get(f"{API}/media/{res['media_id']}", headers=H)).content if out.status_code == 200 else b""
            print(f"{shop} ({who}): sample {up.json().get('seconds')}s pitch {pitch(wav):.0f} Hz | reply engine {res.get('engine')} "
                  f"pitch {pitch(await M.to_wav16k(clone)) if clone else 0:.0f} Hz")
            fake = f"{900000 + i}:TEST-{stamp}"
            await db.settings.update_one({"business_id": bid}, {"$set": {"telegram_token": fake}})
            hdr = {"X-Telegram-Bot-Api-Secret-Token": tg_secret(bid, fake)}
            for n, text in enumerate(["/start", "តើបងឈ្មោះអ្វី? មកពីហាងណា?"]):
                upd = {"message": {"chat": {"id": 5000 + i}, "from": {"first_name": "Client"}, "text": text}}
                assert (await h.post(f"{API}/webhooks/telegram/{bid}", json=upd, headers=hdr)).status_code == 200
                await asyncio.sleep(2 if n == 0 else 25)
            first = {"message": {"chat": {"id": 6000 + i}, "from": {"first_name": "New"}, "text": "មានអាវយឺតទេ?"}}
            await h.post(f"{API}/webhooks/telegram/{bid}", json=first, headers=hdr)
            await asyncio.sleep(25)
            for cid in (5000 + i, 6000 + i):
                conv = await db.conversations.find_one({"business_id": bid, "external_id": str(cid)})
                msgs = await db.messages.find({"conversation_id": conv["id"]}).sort("created_at", 1).to_list(20)
                print("   chat", cid, " | ".join(f"{m['role']}: {m['text'][:70]}" for m in msgs))


asyncio.run(main())
