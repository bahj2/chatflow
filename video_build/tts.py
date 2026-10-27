"""Khmer narration for the tutorial video (one mp3 per scene), soft female voice."""
import asyncio
import json
import os
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402

load_dotenv("/app/backend/.env")
from emergentintegrations.llm.openai import OpenAITextToSpeech  # noqa: E402

KEY = os.environ["EMERGENT_LLM_KEY"]
STYLE = ("Speak in Khmer as a young Cambodian woman with a very soft, gentle, sweet and calm voice. "
         "Warm and friendly, smiling, unhurried pace, clear pronunciation, like a kind shop assistant explaining to a friend.")
OUT = "/app/video_build/audio"
SCENES = json.load(open("/app/video_build/scenes.json"))


async def one(i):
    path = f"{OUT}/{i:02d}.mp3"
    if os.path.exists(path) and "--force" not in sys.argv:
        return
    mp3 = await OpenAITextToSpeech(api_key=KEY).generate_speech(text=SCENES[i]["say"], model="gpt-4o-mini-tts", voice="shimmer",
                                                                 speed=0.95, instructions=STYLE)
    open(path, "wb").write(mp3)
    print("ok", i, flush=True)


async def main():
    os.makedirs(OUT, exist_ok=True)
    only = [int(x) for x in sys.argv[1:] if x.isdigit()] or range(len(SCENES))
    for i in only:
        await one(i)


asyncio.run(main())
