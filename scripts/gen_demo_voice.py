from dotenv import load_dotenv; load_dotenv('/app/backend/.env')
import sys; sys.path.insert(0, '/app/backend')
import asyncio, media as M
async def gen(text, voice, path):
    M.HF_VOICE = voice
    for i in range(90):
        try:
            a = await M.hf_voxcpm(text, timeout=90)
            open(path, "wb").write(a); print("ok", path, len(a), flush=True); return
        except Exception as e:
            print("retry", i, path, str(e)[:80], flush=True); await asyncio.sleep(40)
async def main():
    await gen("យកអាវយឺតកប្បាស ពីរ ផង បង", "A young Cambodian man, casual and friendly", "/app/frontend/public/demo/customer-voice.mp3")
    await gen("ចាស បង! អាវយឺតកប្បាសពណ៌ស ទំហំ M ចំនួនពីរ សរុប ដប់ប្រាំមួយ ដុល្លារ។ សូមស្កេន QR ខាងក្រោម ដើម្បីទូទាត់។", "A warm, friendly young woman", "/app/frontend/public/demo/bot-voice.mp3")
asyncio.run(main())
