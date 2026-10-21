"""ReplyFlow VoxCPM2 voice server: POST /v1/audio/speech (seller-voice cloning) + GET /health."""
import base64
import io
import os
import tempfile
import threading
from typing import Optional

import soundfile as sf
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel


class SpeechIn(BaseModel):
    input: str
    ref_audio: Optional[str] = None  # data:audio/wav;base64,...
    ref_text: Optional[str] = None
    cfg_value: float = 2.0
    inference_timesteps: int = 10


def load_model():
    from voxcpm import VoxCPM
    return VoxCPM.from_pretrained(os.environ.get("VOXCPM_MODEL", "openbmb/VoxCPM2"), load_denoiser=False)


def gpu_name() -> str:
    try:
        import torch
        return torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    except Exception:
        return "unknown"


def create_app(model, api_key: str = "") -> FastAPI:
    app = FastAPI(title="ReplyFlow VoxCPM2")
    lock = threading.Lock()

    def check(auth: str):
        if api_key and auth != f"Bearer {api_key}":
            raise HTTPException(401, "Invalid API key")

    @app.get("/health")
    def health(authorization: str = Header("")):
        check(authorization)
        return {"ok": True, "model": "VoxCPM2", "gpu": gpu_name()}

    @app.post("/v1/audio/speech")
    def speech(body: SpeechIn, authorization: str = Header("")):
        check(authorization)
        text = body.input.strip()
        if not text:
            raise HTTPException(400, "Empty input")
        kw = {"text": text[:2000], "cfg_value": body.cfg_value, "inference_timesteps": body.inference_timesteps}
        ref = None
        try:
            if body.ref_audio:
                ref = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                ref.write(base64.b64decode(body.ref_audio.split(",", 1)[-1]))
                ref.close()
                kw["reference_wav_path"] = ref.name
                if body.ref_text:
                    kw.update(prompt_wav_path=ref.name, prompt_text=body.ref_text)
            with lock:
                wav = model.generate(**kw)
        finally:
            if ref:
                os.unlink(ref.name)
        buf = io.BytesIO()
        sf.write(buf, wav, model.tts_model.sample_rate, format="WAV")
        return Response(buf.getvalue(), media_type="audio/wav")

    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_app(load_model(), os.environ.get("VOXCPM_API_KEY", "")), host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
