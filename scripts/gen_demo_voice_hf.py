"""Make the 7 demo-video clips with the free official VoxCPM2 Hugging Face demo (no Microsoft/Azure voices).

Narrator, customer and seller each get their own designed voice. The first clip of a voice is reused as the clone
reference for that voice's later clips so it stays the same person. Each clip is transcribed back and retried if
the Khmer words don't match. Usage: python3 scripts/gen_demo_voice_hf.py  then  python3 scripts/make_demo_video.py
"""
import asyncio
import os
import sys

sys.path.insert(0, "/app/scripts")
from import_voice_clips import LINES, OUT, M, score  # noqa: E402

VOICES = {
    "narrator": "A confident, energetic young man presenting a TV advert, clear and upbeat",
    "customer": "A cheerful young woman, casual and relaxed, chatting on her phone",
    "seller": M.HF_VOICE,
}
ROLE = {"c1": "customer", "c2": "seller"}
TRIES = 5


async def make(key: str, ref):
    text, role = LINES[key], ROLE.get(key, "narrator")
    best = (0.0, None)
    for n in range(TRIES):
        try:
            mp3 = await (M.hf_voxcpm(text, ref[0], ref[1], timeout=150) if ref else M.hf_voxcpm(text, timeout=150, voice=VOICES[role]))
        except Exception as e:
            print(f"  {key} try {n + 1}: {e!r}"[:200])
            await asyncio.sleep(8)
            continue
        heard = await M.transcribe(mp3)
        sc = score(heard, text)
        print(f"  {key} try {n + 1}: match {sc:.2f}  heard: {heard[:60]}")
        if sc > best[0]:
            best = (sc, mp3)
        if sc >= 0.8:
            break
    if not best[1]:
        raise SystemExit(f"{key}: the VoxCPM2 demo gave no audio")
    return best[1]


async def main(only):
    os.makedirs(OUT, exist_ok=True)
    refs = {}
    for key in LINES:
        role = ROLE.get(key, "narrator")
        if only and key not in only:
            continue
        mp3 = await make(key, refs.get(role))
        open(f"{OUT}/{key}.mp3", "wb").write(mp3)
        if role not in refs:
            refs[role] = (await M.to_wav16k(mp3), LINES[key])
        print(key, role, len(mp3), "bytes")


asyncio.run(main(sys.argv[1:]))
