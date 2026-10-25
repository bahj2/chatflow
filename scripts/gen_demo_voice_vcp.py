"""Make the 7 demo-video clips (n1..n5, c1, c2) with a business's connected Voice Creator Pro (VoxCPM2).

Usage: python3 scripts/gen_demo_voice_vcp.py OWNER_EMAIL [narrator=VOICE_ID] [customer=VOICE_ID] [shop=VOICE_ID]
Voice IDs default to the voice picked in AI Settings → Voice. Then run scripts/make_demo_video.py.
"""
import asyncio
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/scripts")
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
import media as M  # noqa: E402
from import_voice_clips import LINES, OUT  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

ARGS = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)
ROLE = {"c1": "customer", "c2": "shop"}


async def main(email: str):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    user = await db.users.find_one({"email": email.lower()})
    s = await db.settings.find_one({"business_id": user["business_id"]}) if user else None
    if not (s and s.get("vcp_url")):
        raise SystemExit("This business has not connected Voice Creator Pro (AI Settings → Voice).")
    os.makedirs(OUT, exist_ok=True)
    for k, text in LINES.items():
        voice = ARGS.get(ROLE.get(k, "narrator"), s.get("vcp_voice_id", ""))
        ns = SimpleNamespace(vcp_url=s["vcp_url"], vcp_key=s["vcp_key"], vcp_model=s.get("vcp_model", ""), vcp_voice_id=voice, seller_voice_text="")
        mp3 = await M.vcp_speak(ns, text, None, timeout=300)
        open(f"{OUT}/{k}.mp3", "wb").write(mp3)
        print(k, voice or "(default voice)", len(mp3), "bytes")


asyncio.run(main(sys.argv[1]))
