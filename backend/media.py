import asyncio
import io
import json
import os
import re
import subprocess
import tempfile
import uuid
import wave
from datetime import datetime, timezone

import httpx
import imageio_ffmpeg
import requests
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
from emergentintegrations.llm.openai import OpenAISpeechToText, OpenAITextToSpeech

EMERGENT_KEY = os.environ["EMERGENT_LLM_KEY"]
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_NAME = "replyflow"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
KHMER = re.compile(r"[\u1780-\u17D3]")  # Khmer letters/signs only (not ៛ or digits)
VOICES = ["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]")
_storage_key = None


def init_storage(force: bool = False) -> str:
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    r.raise_for_status()
    _storage_key = r.json()["storage_key"]
    return _storage_key


def _put(path: str, data: bytes, content_type: str) -> dict:
    for attempt in range(2):
        r = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": init_storage(force=attempt == 1), "Content-Type": content_type},
                         data=data, timeout=120)
        if r.status_code != 404:
            break
    r.raise_for_status()
    return r.json()


def _get(path: str) -> tuple:
    for attempt in range(2):
        r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": init_storage(force=attempt == 1)}, timeout=60)
        if r.status_code != 404:
            break
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")


EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "audio/mpeg": "mp3", "audio/wav": "wav", "audio/ogg": "ogg"}


async def save_media(db, bid: str, data: bytes, content_type: str, kind: str) -> dict:
    path = f"{APP_NAME}/{bid}/{kind}/{uuid.uuid4()}.{EXT.get(content_type, 'bin')}"
    res = await asyncio.to_thread(_put, path, data, content_type)
    doc = {"id": str(uuid.uuid4()), "business_id": bid, "storage_path": res["path"], "content_type": content_type,
           "size": len(data), "kind": kind, "is_deleted": False, "created_at": datetime.now(timezone.utc).isoformat()}
    await db.media.insert_one(dict(doc))
    return doc


async def load_media(db, mid: str):
    doc = await db.media.find_one({"id": mid, "is_deleted": False}, {"_id": 0})
    if not doc:
        return None, None
    data, _ = await asyncio.to_thread(_get, doc["storage_path"])
    return data, doc


def _ffmpeg(data: bytes, args: list) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".in") as src, tempfile.NamedTemporaryFile(suffix=".out") as dst:
        src.write(data)
        src.flush()
        fmt = args[-1]
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", src.name, *args[:-1], "-f", fmt, dst.name], check=True, timeout=60)
        return open(dst.name, "rb").read()


async def to_mp3(data: bytes) -> bytes:
    return await asyncio.to_thread(_ffmpeg, data, ["-vn", "-ac", "1", "-b:a", "64k", "mp3"])


async def to_wav16k(data: bytes) -> bytes:
    return await asyncio.to_thread(_ffmpeg, data, ["-vn", "-ac", "1", "-ar", "16000", "wav"])


async def gemini_transcribe(mp3: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(mp3)
        path = f.name
    try:
        chat = LlmChat(api_key=EMERGENT_KEY, session_id=str(uuid.uuid4()), system_message="You are an expert multilingual speech transcriber.").with_model("gemini", "gemini-3-flash-preview")
        out = await chat.send_message(UserMessage(
            text="Transcribe this voice message exactly, in its original language and native script (Khmer script for Khmer, never romanize). "
                 "Output only the transcript. If there is no speech, output nothing.",
            file_contents=[FileContentWithMimeType(file_path=path, mime_type="audio/mpeg")]))
        return (out or "").strip()
    finally:
        os.unlink(path)


async def whisper_transcribe(mp3: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
        f.write(mp3)
        f.flush()
        with open(f.name, "rb") as fh:
            res = await OpenAISpeechToText(api_key=EMERGENT_KEY).transcribe(file=fh, model="whisper-1", response_format="json")
    return (res.text or "").strip()


async def transcribe(mp3: bytes) -> str:
    try:
        return await gemini_transcribe(mp3)
    except Exception as e:
        print(f"Gemini transcription failed, using Whisper: {e}")
        return await whisper_transcribe(mp3)


HF_VOXCPM = "https://openbmb-voxcpm-demo.hf.space"
HF_VOICE = "A warm, friendly young woman"
HF_TIMEOUT = 60


def wav_seconds(wav: bytes) -> float:
    with wave.open(io.BytesIO(wav)) as w:
        return w.getnframes() / float(w.getframerate())


async def hf_voxcpm(text: str, ref_wav: bytes = None, ref_text: str = "", timeout: float = HF_TIMEOUT) -> bytes:
    """Khmer speech from the free official VoxCPM2 Hugging Face demo: seller-voice clone if a sample is given, else the default voice."""
    async def run():
        async with httpx.AsyncClient(timeout=timeout) as h:
            ref, clone_text = None, ""
            if ref_wav:
                up = await h.post(f"{HF_VOXCPM}/gradio_api/upload", files={"files": ("seller.wav", ref_wav, "audio/wav")})
                up.raise_for_status()
                ref, clone_text = {"path": up.json()[0], "meta": {"_type": "gradio.FileData"}}, ref_text.strip()
            data = [text, "" if ref else HF_VOICE, ref, bool(clone_text), clone_text, 2.0, False, False]
            r = await h.post(f"{HF_VOXCPM}/gradio_api/call/generate", json={"data": data})
            r.raise_for_status()
            eid, event = r.json()["event_id"], None
            async with h.stream("GET", f"{HF_VOXCPM}/gradio_api/call/generate/{eid}") as s:
                async for line in s.aiter_lines():
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:") and event == "error":
                        raise RuntimeError(f"VoxCPM2 demo error: {line[5:].strip()[:200]}")
                    elif line.startswith("data:") and event == "complete":
                        url = json.loads(line[5:])[0]["url"]
                        if not url.startswith(HF_VOXCPM + "/"):
                            raise RuntimeError("VoxCPM2 demo returned an unexpected file link")
                        a = await h.get(url)
                        a.raise_for_status()
                        return a.content
            raise RuntimeError("VoxCPM2 demo returned no audio")
    return await to_mp3(await asyncio.wait_for(run(), timeout))


async def seller_ref(db, s):
    if not s.seller_voice_media_id:
        return None
    try:
        return (await load_media(db, s.seller_voice_media_id))[0]
    except Exception as e:
        print(f"Seller voice sample unavailable, using default voice: {e}")
        return None


async def speak(db, s, text: str, timeout: float = HF_TIMEOUT) -> tuple:
    """Returns (mp3_bytes, engine). Khmer uses only the free HF VoxCPM2 demo and raises if it is down (caller sends text only)."""
    text = EMOJI.sub("", text).strip()
    if KHMER.search(text):
        ref = await seller_ref(db, s)
        if ref:
            return await hf_voxcpm(text, ref, s.seller_voice_text, timeout), "voxcpm2-hf-clone"
        return await hf_voxcpm(text, timeout=timeout), "voxcpm2-hf"
    audio = await OpenAITextToSpeech(api_key=EMERGENT_KEY).generate_speech(text=text[:4000], model="tts-1", voice=s.voice if s.voice in VOICES else "nova")
    return audio, "openai"
