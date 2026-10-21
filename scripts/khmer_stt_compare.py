import asyncio, os, sys, tempfile, uuid
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient
import media as M
from emergentintegrations.llm.openai import OpenAISpeechToText
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType

db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
KEY = os.environ["EMERGENT_LLM_KEY"]

async def stt(mp3, model, lang=None, prompt=None):
    with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
        f.write(mp3); f.flush()
        with open(f.name, "rb") as fh:
            kw = {"file": fh, "model": model, "response_format": "json"}
            if lang: kw["language"] = lang
            if prompt: kw["prompt"] = prompt
            return (await OpenAISpeechToText(api_key=KEY).transcribe(**kw)).text

async def gemini(mp3, model):
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(mp3); path = f.name
    chat = LlmChat(api_key=KEY, session_id=str(uuid.uuid4()), system_message="You are an expert Khmer speech transcriber.").with_model("gemini", model)
    msg = UserMessage(text="Transcribe this voice message exactly, in the original language and script (Khmer script for Khmer). Output only the transcript.",
                      file_contents=[FileContentWithMimeType(file_path=path, mime_type="audio/mpeg")])
    return await chat.send_message(msg)

async def main():
    b = "da4f34c0-2f00-41e1-ab8c-86332eada73f"
    ids = [a["media_id"] async for m in db.messages.find({"business_id": b, "role": "user", "attachments.type": "audio"}) for a in m["attachments"] if a["type"] == "audio"]
    for mid in ids:
        mp3, _ = await M.load_media(db, mid)
        print("=== media", mid[:8], len(mp3), "bytes")
        for label, coro in [("whisper-1 auto", stt(mp3, "whisper-1")), ("whisper-1 km", stt(mp3, "whisper-1", "km")),
                            ("gpt-4o-transcribe km", stt(mp3, "gpt-4o-transcribe", "km")), ("gpt-4o-mini-transcribe km", stt(mp3, "gpt-4o-mini-transcribe", "km")),
                            ("gemini-3-flash", gemini(mp3, "gemini-3-flash-preview")), ("gemini-2.5-pro", gemini(mp3, "gemini-2.5-pro"))]:
            try:
                print(f"{label:28s}", (await coro).strip()[:200])
            except Exception as e:
                print(f"{label:28s} ERROR {str(e)[:150]}")

asyncio.run(main())
