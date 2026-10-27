"""Records the tutorial screen tour (one continuous video) and logs when each scene starts."""
import asyncio
import json
import subprocess
import time

import httpx
from playwright.async_api import async_playwright

import imageio_ffmpeg

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
EMAIL, PW = "tour@replyflow.com", "TourDemo2026!"
SCENES = json.load(open("/app/video_build/scenes.json"))
FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1280, 720


def dur(i):
    out = subprocess.run([FF, "-i", f"/app/video_build/audio/{i:02d}.mp3"], capture_output=True, text=True).stderr
    h, m, s = out.split("Duration: ")[1].split(",")[0].split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


OVERLAY = """
(() => {
  const css = document.createElement('style');
  css.textContent = `
  #tour-cap{position:fixed;left:50%;bottom:34px;transform:translateX(-50%);z-index:2147483647;max-width:1040px;width:max-content;
    padding:14px 26px;border-radius:18px;background:rgba(10,12,30,.82);backdrop-filter:blur(10px);color:#fff;
    font:600 23px/1.55 'Noto Sans Khmer','Manrope',sans-serif;text-align:center;box-shadow:0 12px 40px rgba(0,0,0,.35);
    transition:opacity .35s ease;opacity:0;pointer-events:none}
  #tour-cap.on{opacity:1}
  #tour-step{position:fixed;top:18px;right:22px;z-index:2147483647;padding:6px 14px;border-radius:999px;
    background:linear-gradient(120deg,#2563EB,#4F46E5 55%,#7C3AED);color:#fff;font:700 13px 'Manrope',sans-serif;pointer-events:none}
  #tour-cur{position:fixed;z-index:2147483647;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;
    background:rgba(79,70,229,.35);border:2px solid #4F46E5;pointer-events:none;transition:transform .15s ease;left:-50px;top:-50px}
  #tour-cur.down{transform:scale(.7);background:rgba(79,70,229,.6)}`;
  const add = () => {
    if (document.getElementById('tour-cap')) return;
    document.head.appendChild(css);
    for (const id of ['tour-cap','tour-step','tour-cur']) { const d = document.createElement('div'); d.id = id; document.body.appendChild(d); }
    document.getElementById('tour-step').style.display = 'none';
    const c = document.getElementById('tour-cur');
    addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    addEventListener('mousedown', () => c.classList.add('down'), true);
    addEventListener('mouseup', () => c.classList.remove('down'), true);
    const s = sessionStorage.getItem('tourCap'); if (s) window.tourCap(s, sessionStorage.getItem('tourStep'));
  };
  window.tourCap = (text, step) => {
    sessionStorage.setItem('tourCap', text || ''); sessionStorage.setItem('tourStep', step || '');
    const cap = document.getElementById('tour-cap'); if (!cap) return;
    cap.textContent = text || ''; cap.classList.toggle('on', !!text);
    const st = document.getElementById('tour-step'); st.textContent = step || ''; st.style.display = step ? 'block' : 'none';
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', add); else add();
})();
"""


class Tour:
    def __init__(self, page):
        self.page, self.t0, self.starts = page, time.monotonic(), []

    async def cap(self, i):
        step = "" if i in (0, len(SCENES) - 1) else f"ជំហាន {i}"
        await self.page.evaluate("([t, s]) => window.tourCap && window.tourCap(t, s)", [SCENES[i]["say"], step])

    async def go(self, path):
        await self.page.goto(BASE + path, wait_until="load")
        await self.page.wait_for_timeout(700)
        await self.page.wait_for_timeout(500)

    async def move(self, sel, click=False):
        el = self.page.locator(sel).first
        await el.scroll_into_view_if_needed()
        b = await el.bounding_box()
        if not b:
            return
        await self.page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=25)
        await self.page.wait_for_timeout(250)
        if click:
            await el.click()

    async def type(self, sel, text):
        await self.move(sel, click=True)
        await self.page.locator(sel).first.fill("")
        await self.page.keyboard.type(text, delay=55)

    async def scroll(self, dy, steps=20, ms=40):
        for _ in range(steps):
            await self.page.mouse.wheel(0, dy / steps)
            await self.page.wait_for_timeout(ms)

    async def scene(self, i, fn):
        start = time.monotonic()
        self.starts.append(start - self.t0)
        await fn()
        left = dur(i) + 0.9 - (time.monotonic() - start)
        if left > 0:
            await self.page.wait_for_timeout(int(left * 1000))


async def main():
    async with httpx.AsyncClient(timeout=30) as h:
        token = (await h.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PW})).json()["token"]
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/pw-browsers/chromium_headless_shell-1208/chrome-linux/headless_shell")
        ctx = await b.new_context(viewport={"width": W, "height": H}, record_video_dir="/app/video_build/raw", record_video_size={"width": W, "height": H})
        await ctx.add_init_script("try{localStorage.setItem('rf_theme','light')}catch(e){}")
        await ctx.add_init_script(OVERLAY)
        page = await ctx.new_page()
        t = Tour(page)
        pg = page

        async def intro():
            await t.go("/")
            await t.cap(0)
            await pg.wait_for_timeout(2500)
            await t.scroll(700, 30, 60)
            await pg.wait_for_timeout(1500)
            await t.scroll(500, 25, 60)

        async def signup():
            await t.go("/signup")
            await t.cap(1)
            await t.type("[data-testid=signup-business-input]", "Sokha Fashion")
            await t.type("[data-testid=signup-email-input]", "sokha@gmail.com")
            await t.type("[data-testid=signup-password-input]", "sokha2026")
            await t.move("[data-testid=signup-submit-btn]")
            await pg.evaluate("t => localStorage.setItem('rf_token', t)", token)

        async def settings():
            await t.go("/dashboard/settings")
            await t.cap(2)
            await t.move("[data-testid=settings-tab-business]")
            await t.move("[data-testid=business-info-input]", click=True)
            await pg.keyboard.press("End")
            await pg.keyboard.type(" Free gift wrap.", delay=60)
            await t.move("[data-testid=assistant-name-input]")
            await t.move("[data-testid=save-settings-btn]")

        async def channels():
            await t.go("/dashboard/channels")
            await t.cap(3)
            await t.type("[data-testid=telegram-token-input]", "7712345678:AAHk-Sokha-Demo-Token")
            await t.move("[data-testid=save-telegram-btn]")

        async def products():
            await t.go("/dashboard/products")
            await t.cap(4)
            await pg.wait_for_timeout(800)
            for k in ("in", "low", "out"):
                await t.move(f"[data-testid=products-summary-{k}]")
            cards = pg.locator("[data-testid^=product-stock-plus-]")
            if await cards.count():
                await t.move("[data-testid^=product-stock-plus-]", click=True)
            await t.move("[data-testid=add-product-btn]", click=True)
            await pg.wait_for_timeout(500)
            await t.type("[data-testid=product-name-input]", "Pink Summer Dress")
            await t.type("[data-testid=product-price-input]", "$19")
            await t.type("[data-testid=product-category-input]", "Clothes")
            await t.move("[data-testid=product-stock-switch]", click=True)
            await pg.wait_for_timeout(600)
            await t.move("[data-testid=product-cancel-btn]", click=True)

        async def test_ai():
            await t.go("/dashboard/settings")
            await t.cap(5)
            await t.move("[data-testid=settings-tab-ai]", click=True)
            await pg.wait_for_timeout(400)
            await t.type("[data-testid=ai-test-input]", "មានកាបូបខ្មៅទេបង?")
            await t.move("[data-testid=ai-test-btn]", click=True)
            try:
                await pg.wait_for_selector("[data-testid=ai-test-reply]", timeout=25000)
                await pg.locator("[data-testid=ai-test-reply]").scroll_into_view_if_needed()
            except Exception as e:
                print("ai test reply missing", e)
            await pg.wait_for_timeout(1500)

        async def inbox():
            await t.go("/dashboard")
            await t.cap(6)
            await t.move("[data-testid^=conversation-item-]:has-text('Dara')", click=True)
            await pg.wait_for_timeout(1500)
            await t.move("[data-testid=ai-toggle-switch]")
            await pg.wait_for_timeout(800)
            await t.move("[data-testid^=conversation-item-]:has-text('Sreyneang')", click=True)

        async def orders():
            await t.go("/dashboard/orders")
            await t.cap(7)
            await t.move("[data-testid^=order-total-]")
            await pg.wait_for_timeout(1000)

        async def billing():
            await t.go("/dashboard/billing")
            await t.cap(8)
            await t.move("[data-testid=billing-current]")
            await t.move("[data-testid=plan-card-starter]")
            await t.move("[data-testid=plan-choose-pro]", click=True)
            try:
                await pg.wait_for_selector("[data-testid=billing-pay-qr]", timeout=20000)
            except Exception as e:
                print("pay dialog missing", e)

        async def outro():
            await t.go("/#pricing")
            await t.cap(9)
            await pg.wait_for_timeout(600)
            await pg.locator("#pricing").scroll_into_view_if_needed()
            await t.move("[data-testid=pricing-trial-btn]")

        for i, fn in enumerate([intro, signup, settings, channels, products, test_ai, inbox, orders, billing, outro]):
            await t.scene(i, fn)
            print("scene", i, round(t.starts[-1], 2), flush=True)
        await page.wait_for_timeout(1200)
        total = time.monotonic() - t.t0
        vpath = "/app/video_build/tour_raw.webm"
        await page.close()
        await page.video.save_as(vpath)
        await ctx.close()
        await b.close()
    json.dump({"video": vpath, "starts": t.starts, "total": total}, open("/app/video_build/timeline.json", "w"))
    print("done", vpath, total)


asyncio.run(main())
