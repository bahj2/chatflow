# Generates test fixtures (speech audio + product image) into /tmp/rf_fixtures
import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from emergentintegrations.llm.openai import OpenAITextToSpeech
from PIL import Image

OUT = Path("/tmp/rf_fixtures"); OUT.mkdir(exist_ok=True)


async def main():
    tts = OpenAITextToSpeech(api_key=os.environ["EMERGENT_LLM_KEY"])
    a = await tts.generate_speech(text="Hi, do you sell ceramic coffee mugs? How much is one?", model="tts-1", voice="alloy", response_format="opus")
    (OUT / "mug_question.ogg").write_bytes(a)
    b = await tts.generate_speech(text="What time do you open on Saturday?", model="tts-1", voice="alloy")
    (OUT / "hours_question.mp3").write_bytes(b)
    Image.new("RGB", (300, 300), (200, 120, 60)).save(OUT / "mug.png")
    print("ok", len(a), len(b))

asyncio.run(main())
