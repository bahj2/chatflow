# Generates Khmer + English voice fixtures for test_iter7_khmer_voice.py
import asyncio
import os

import edge_tts

FX = "/tmp/rf_fixtures"


async def tts(text, voice, path):
    out = b""
    async for c in edge_tts.Communicate(text, voice).stream():
        if c["type"] == "audio":
            out += c["data"]
    open(path, "wb").write(out)
    print(path, len(out))


async def main():
    os.makedirs(FX, exist_ok=True)
    await tts("សួស្តីបង បងមានលក់អីដែរ?", "km-KH-PisethNeural", f"{FX}/khmer_q.mp3")
    await tts("Hello, what kinds of coffee do you sell and how much is a latte?", "en-US-GuyNeural", f"{FX}/english_q.mp3")

asyncio.run(main())
