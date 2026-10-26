"""Check: one Telegram bot / Facebook page can belong to only one shop (no mixed-up shops)."""
import asyncio
import os
import sys
import time

import httpx

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
import server  # noqa: E402

API = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0] + "/api"


async def main():
    stamp = str(int(time.time()))[-6:]
    bot = f"77{stamp}"
    async with httpx.AsyncClient(timeout=60) as h:
        shops = []
        for i in (1, 2):
            r = (await h.post(f"{API}/auth/register", json={"email": f"tok{i}-{stamp}@example.com", "password": "toktest123", "business_name": f"Token Shop {i}"})).json()
            shops.append(({"Authorization": f"Bearer {r['token']}"}, r["user"]["business_id"]))

        async def put(i, **kw):
            H = shops[i][0]
            cur = (await h.get(f"{API}/settings", headers=H)).json()
            cur.update(kw)
            r = await h.put(f"{API}/settings", headers=H, json=cur)
            return r.status_code, r.json().get("detail", "")

        print("A saves bot           ", await put(0, telegram_token=f"{bot}:AAA-first"))
        print("B same bot            ", await put(1, telegram_token=f"{bot}:AAA-first"))
        print("B same bot new secret ", await put(1, telegram_token=f"{bot}:BBB-revoked"))
        print("B own bot             ", await put(1, telegram_token=f"88{stamp}:CCC"))
        print("A re-saves own bot    ", await put(0, telegram_token=f"{bot}:AAA-first", greeting="hi"))
        r = await h.post(f"{API}/channels/telegram/connect", headers=shops[1][0], json={"base_url": "https://example.com"})
        print("B connect own (fake)  ", r.status_code, r.json().get("detail", "")[:60])
    # Facebook: Graph lookups need real tokens, so check write_settings directly with a stubbed page lookup
    server.fb_page_id = lambda token: asyncio.sleep(0, result="PAGE-" + token.split("-")[0])
    for i, tok in ((0, "P1-a"), (1, "P1-b"), (1, "P2-a")):
        bid = shops[i][1]
        s = await server.get_settings(bid)
        try:
            out = await server.write_settings(s.model_copy(update={"fb_page_token": tok}), {"business_id": bid})
            print(f"shop {'AB'[i]} page {tok:5}", 200, out["fb_page_id"])
        except server.HTTPException as e:
            print(f"shop {'AB'[i]} page {tok:5}", e.status_code, e.detail)
    for _, bid in shops:
        for c in ("settings", "businesses"):
            await server.db[c].delete_many({"business_id": bid} if c == "settings" else {"id": bid})
        await server.db.users.delete_many({"business_id": bid})


asyncio.run(main())
