import asyncio
import base64
import io
import json
import os
import re
import subprocess
import tempfile
import time
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


# ---------- Voice Creator Pro desktop app (seller's own computer, reached through a public tunnel link) ----------
VCP_HEADERS = {"ngrok-skip-browser-warning": "1", "User-Agent": "ReplyFlow"}
VCP_REF_MAX = 15  # the clone endpoint accepts 3-15 s of reference audio
VCP_UNREACHABLE = ("Cannot reach Voice Creator Pro on your computer. Is the computer awake, the app open with HTTP API on, and the tunnel running? "
                   "(Quick tunnel links change after every restart.)")


class VcpError(Exception):
    pass


def _vcp_auth(key: str) -> dict:
    return {**VCP_HEADERS, "X-API-Key": key}


def _items(data, key: str) -> list:
    if isinstance(data, dict):
        data = data.get(key, data.get("items", data.get("data", [])))
    return data if isinstance(data, list) else []


def _find_audio(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and "audio" in k.lower() and len(v) > 200:
                return base64.b64decode(v.split(",", 1)[-1])
        obj = [v for v in obj.values() if isinstance(v, (dict, list))]
    for v in obj if isinstance(obj, list) else []:
        if (a := _find_audio(v)):
            return a
    return None


def _voxcpm_family(data) -> str:
    models = data.get("models", data) if isinstance(data, dict) else data
    if isinstance(models, dict):
        models = [{"model_family": k, **(v if isinstance(v, dict) else {})} for k, v in models.items()]
    for m in models if isinstance(models, list) else []:
        if isinstance(m, str) and "voxcpm" in m.lower():
            return m
        if isinstance(m, dict) and "voxcpm" in json.dumps(m).lower():
            return str(m.get("model_family") or m.get("family") or m.get("id") or m.get("name") or "")
    return ""


async def vcp_connect(url: str, key: str) -> dict:
    """Checks the link really is Voice Creator Pro with an API key turned on; returns its saved voices and the VoxCPM2 model id."""
    async with httpx.AsyncClient(timeout=25, headers=VCP_HEADERS) as h:
        try:
            r = await h.get(f"{url}/api/v1/health")
        except httpx.HTTPError:
            raise VcpError(VCP_UNREACHABLE)
        if r.status_code >= 502:
            raise VcpError(VCP_UNREACHABLE)
        if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
            raise VcpError('This link does not answer like Voice Creator Pro. Turn on "Enable HTTP API" in its Settings and point the tunnel to port 8100.')
        if (await h.get(f"{url}/api/v1/voices")).status_code == 200:
            raise VcpError("Set an API key in Voice Creator Pro → Settings first, so only ReplyFlow can use your computer.")
        r = await h.get(f"{url}/api/v1/voices", headers=_vcp_auth(key))
        if r.status_code in (401, 403):
            raise VcpError("Wrong API key. Copy it again from Voice Creator Pro → Settings.")
        if r.status_code != 200:
            raise VcpError(f"Voice Creator Pro answered with error {r.status_code}.")
        voices = [{"id": str(v.get("id") or v.get("voice_id")), "name": str(v.get("name") or v.get("id") or v.get("voice_id"))[:80]}
                  for v in _items(r.json(), "voices") if isinstance(v, dict) and (v.get("id") or v.get("voice_id"))][:200]
        try:
            model = _voxcpm_family((await h.get(f"{url}/api/v1/models", headers=_vcp_auth(key))).json())
        except (httpx.HTTPError, ValueError):
            model = ""
    return {"voices": voices, "model": model}


async def vcp_speak(s, text: str, ref_wav: bytes = None, timeout: float = HF_TIMEOUT) -> bytes:
    """Khmer speech from the seller's Voice Creator Pro: saved voice, else the ReplyFlow seller sample, else a designed default voice."""
    body = {"target_text": text, "language": "Auto", **({"model_family": s.vcp_model} if s.vcp_model else {})}
    if s.vcp_voice_id:
        mode, body["voice_id"] = "clone", s.vcp_voice_id
    elif ref_wav:
        short = wav_seconds(ref_wav) <= VCP_REF_MAX
        clip = ref_wav if short else await asyncio.to_thread(_ffmpeg, ref_wav, ["-t", str(VCP_REF_MAX), "wav"])
        mode = "clone"
        body.update(ref_audio_base64=base64.b64encode(clip).decode(), ref_text=s.seller_voice_text if short else "")
    else:
        mode, body["instruct_text"] = "design", HF_VOICE

    async def run():
        async with httpx.AsyncClient(timeout=timeout, headers=_vcp_auth(s.vcp_key)) as h:
            r = await h.post(f"{s.vcp_url}/api/v1/generation/{mode}", params={"sync": "true"}, json=body)
        if r.status_code in (401, 403):
            raise VcpError("Voice Creator Pro refused the API key. Connect it again in Settings.")
        r.raise_for_status()
        if r.headers.get("content-type", "").startswith("audio/"):
            return r.content
        audio = _find_audio(r.json())
        if not audio:
            raise VcpError("Voice Creator Pro answered without audio.")
        return audio
    return await to_mp3(await asyncio.wait_for(run(), timeout))


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
    """Returns (mp3_bytes, engine). Khmer: the seller's Voice Creator Pro first (if connected), then the free HF VoxCPM2 demo; raises if both fail (caller sends text only)."""
    text = EMOJI.sub("", text).strip()
    if KHMER.search(text):
        ref = await seller_ref(db, s)
        if s.vcp_url:
            t0 = time.monotonic()
            try:
                return await vcp_speak(s, text, ref, timeout), "voxcpm2-vcp"
            except Exception as e:
                print(f"Voice Creator Pro failed, trying the Hugging Face demo: {e!r}")
            timeout -= time.monotonic() - t0
            if timeout < 10:
                raise RuntimeError("Voice Creator Pro took too long; no time left for the Hugging Face demo")
        if ref:
            return await hf_voxcpm(text, ref, s.seller_voice_text, timeout), "voxcpm2-hf-clone"
        return await hf_voxcpm(text, timeout=timeout), "voxcpm2-hf"
    audio = await OpenAITextToSpeech(api_key=EMERGENT_KEY).generate_speech(text=text[:4000], model="tts-1", voice=s.voice if s.voice in VOICES else "nova")
    return audio, "openai"
