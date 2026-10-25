"""Test stand-in for the Voice Creator Pro desktop HTTP API (never used by the app itself).

Usage: python3 scripts/mock_vcp.py [port=8199] [key=test-key] [delay=0]
GET /_calls lists the generation requests received (reference audio replaced by its length).
"""
import asyncio
import base64
import io
import math
import struct
import sys
import wave

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

ARGS = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
KEY = ARGS.get("key", "test-key")
DELAY = float(ARGS.get("delay", "0"))
app = FastAPI()
calls = []


def tone(secs: float = 1.5, sr: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / sr))) for i in range(int(secs * sr))))
    return buf.getvalue()


def authed(r: Request) -> bool:
    return KEY in (r.headers.get("x-api-key"), r.query_params.get("api_key"), r.headers.get("authorization", "")[7:])


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}


@app.get("/api/v1/voices")
async def voices(r: Request):
    if not authed(r):
        return JSONResponse({"detail": "Invalid API key"}, 401)
    return {"voices": [{"id": "v_rasmey", "name": "Rasmey (cloned)", "type": "clone"}, {"id": "v_narrator", "name": "Khmer narrator", "type": "design"}]}


@app.get("/api/v1/models")
async def models(r: Request):
    if not authed(r):
        return JSONResponse({"detail": "Invalid API key"}, 401)
    return {"models": [{"model_family": "qwen3-tts", "name": "Qwen3-TTS"}, {"model_family": "voxcpm2", "name": "VoxCPM2"}]}


@app.post("/api/v1/generation/{mode}")
async def generate(mode: str, r: Request):
    if not authed(r):
        return JSONResponse({"detail": "Invalid API key"}, 401)
    body = await r.json()
    if not body.get("target_text"):
        return JSONResponse({"detail": "target_text required"}, 422)
    ref = body.pop("ref_audio_base64", None)
    calls.append({"mode": mode, "sync": r.query_params.get("sync"), "ref_audio_bytes": len(base64.b64decode(ref)) if ref else 0, **body})
    await asyncio.sleep(DELAY)
    return {"status": "completed", "result": {"audio_base64": base64.b64encode(tone()).decode(), "sample_rate": 24000}}


@app.get("/_calls")
async def get_calls():
    return calls


@app.api_route("/{path:path}", methods=["GET", "POST"])
async def spa(path: str):
    return HTMLResponse("<!doctype html><html><body>Voice Creator Pro</body></html>")


uvicorn.run(app, host="0.0.0.0", port=int(ARGS.get("port", "8199")), log_level="warning")
