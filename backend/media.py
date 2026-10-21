import asyncio
import base64
import os
import re
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone

import httpx
import imageio_ffmpeg
import requests
from emergentintegrations.llm.openai import OpenAISpeechToText, OpenAITextToSpeech

EMERGENT_KEY = os.environ["EMERGENT_LLM_KEY"]
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_NAME = "replyflow"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
KHMER = re.compile(r"[\u1780-\u17FF]")
VOICES = ["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]
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


async def transcribe(mp3: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
        f.write(mp3)
        f.flush()
        with open(f.name, "rb") as fh:
            res = await OpenAISpeechToText(api_key=EMERGENT_KEY).transcribe(file=fh, model="whisper-1", response_format="json")
    return (res.text or "").strip()


async def voxcpm_tts(s, text: str, ref_wav: bytes) -> bytes:
    body = {"model": "openbmb/VoxCPM2", "input": text, "response_format": "wav"}
    if ref_wav:
        body["ref_audio"] = "data:audio/wav;base64," + base64.b64encode(ref_wav).decode()
        if s.seller_voice_text:
            body["ref_text"] = s.seller_voice_text
    headers = {"Authorization": f"Bearer {s.voxcpm_key}"} if s.voxcpm_key else {}
    async with httpx.AsyncClient(timeout=120) as h:
        r = await h.post(f"{s.voxcpm_url.rstrip('/')}/v1/audio/speech", json=body, headers=headers)
    r.raise_for_status()
    return await to_mp3(r.content)


async def speak(db, s, text: str) -> tuple:
    """Returns (mp3_bytes, engine)."""
    use_vox = s.voxcpm_url and (s.voxcpm_for == "all" or KHMER.search(text))
    if use_vox:
        try:
            ref = None
            if s.seller_voice_media_id:
                ref, _ = await load_media(db, s.seller_voice_media_id)
            return await voxcpm_tts(s, text, ref), "voxcpm2"
        except Exception as e:  # fall back to OpenAI voice
            print(f"VoxCPM2 failed, falling back to OpenAI: {e}")
    audio = await OpenAITextToSpeech(api_key=EMERGENT_KEY).generate_speech(text=text[:4000], model="tts-1", voice=s.voice if s.voice in VOICES else "nova")
    return audio, "openai"
