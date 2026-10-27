from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel

import billing as B
import media as M
from core import db, logger, get_settings, current_user, require_pro

router = APIRouter(prefix="/api")


class VoiceTestIn(BaseModel):
    text: str
    voice: Optional[Literal["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]] = None

@router.post("/settings/seller-voice")
async def seller_voice(file: UploadFile = File(...), text: str = Form("", max_length=500), user=Depends(current_user)):
    await require_pro(user["business_id"])
    data = await file.read()
    if not data or len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "Voice sample must be under 10 MB")
    try:
        wav = await M.to_wav16k(data)
        secs = M.wav_seconds(wav)
    except Exception:
        raise HTTPException(400, "Could not read this audio file")
    if not 5 <= secs <= 30.5:
        raise HTTPException(400, f"The sample is {secs:.0f} seconds. Please use 5–30 seconds of clear speech.")
    try:
        text = text.strip() or await M.transcribe(await M.to_mp3(data))
    except Exception as e:
        logger.warning("seller voice transcription failed: %s", e)
        raise HTTPException(424, "Could not write down the words in this sample. Please try again.")
    if not text.strip():
        raise HTTPException(400, "No speech found in this sample. Please record the seller speaking clearly.")
    doc = await M.save_media(db, user["business_id"], wav, "audio/wav", "seller_voice")
    await db.settings.update_one({"business_id": user["business_id"]}, {"$set": {"seller_voice_media_id": doc["id"], "seller_voice_text": text}})
    return {"media_id": doc["id"], "text": text, "seconds": round(secs, 1)}


@router.delete("/settings/seller-voice")
async def delete_seller_voice(user=Depends(current_user)):
    await db.settings.update_one({"business_id": user["business_id"]}, {"$set": {"seller_voice_media_id": "", "seller_voice_text": ""}})
    return {"ok": True}


@router.post("/voice/test")
async def voice_test(body: VoiceTestIn, user=Depends(current_user)):
    await require_pro(user["business_id"])
    s = B.effective(await get_settings(user["business_id"]), await B.sub_status(db, user["business_id"]))
    if body.voice:
        s = s.model_copy(update={"voice": body.voice})
    try:
        audio, engine = await M.speak(db, s, body.text[:500], timeout=50)  # stay under the 60 s proxy limit
    except Exception as e:
        logger.warning("voice test failed: %r", e)
        if M.KHMER.search(body.text):
            raise HTTPException(424, "The free VoxCPM2 Khmer voice (Hugging Face demo) is busy or down right now. "
                                     "Customers get the reply as text until it is back. Try again in a minute.")
        raise HTTPException(424, "Voice generation failed. Please try again.")
    doc = await M.save_media(db, user["business_id"], audio, "audio/mpeg", "voice_test")
    return {"media_id": doc["id"], "engine": engine}
