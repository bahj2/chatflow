"""Import the user's voice clips (any names/formats) into /app/frontend/public/demo/voice/{n1..n5,c1,c2}.mp3.

Each file is transcribed and matched to the closest script line, so the user does not need to rename anything.
Usage: python3 scripts/import_voice_clips.py FILE [FILE ...]
"""
import asyncio
import difflib
import os
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
import media as M  # noqa: E402

OUT = "/app/frontend/public/demo/voice"
LINES = {
    "n1": "អតិថិជនផ្ញើសារមកម៉ោង ១១ យប់ ហើយអ្នកកំពុងគេង?",
    "n2": "រីផ្លាយហ្វ្លូ ឆ្លើយជំនួសអ្នកភ្លាមៗ ជាភាសាខ្មែរ ហើយបង្ហាញរូបទំនិញដោយខ្លួនឯង។",
    "n3": "អតិថិជនផ្ញើសារជាសំឡេង? អេអាយស្ដាប់យល់ ហើយឆ្លើយតបវិញជាសំឡេង។",
    "n4": "ពេលអតិថិជនសម្រេចចិត្តទិញ អេអាយផ្ញើ KHQR តាមចំនួនទឹកប្រាក់ពិតប្រាកដ ហើយបញ្ជាក់ការទូទាត់ភ្លាមៗ។",
    "n5": "រីផ្លាយហ្វ្លូ ជួយលក់ជំនួសអ្នក ២៤ ម៉ោង លើតេឡេក្រាម និងមែសសេនជ័រ។ សាកល្បងថ្ងៃនេះ!",
    "c1": "យកអាវយឺតកប្បាស ពីរ ផង បង",
    "c2": "ចាស បង! អាវយឺតកប្បាសពណ៌ស ទំហំ M ចំនួនពីរ សរុប ដប់ប្រាំមួយ ដុល្លារ។ សូមស្កេន QR ខាងក្រោម ដើម្បីទូទាត់។",
}


def score(a: str, b: str) -> float:
    strip = lambda t: "".join(ch for ch in t if not ch.isspace() and ch not in "!?។,.")  # noqa: E731
    return difflib.SequenceMatcher(None, strip(a), strip(b)).ratio()


async def main(files):
    os.makedirs(OUT, exist_ok=True)
    found = {}
    for f in files:
        mp3 = await M.to_mp3(open(f, "rb").read())
        text = await M.transcribe(mp3)
        best = max(LINES, key=lambda k: score(text, LINES[k]))
        print(f"{os.path.basename(f)} -> {best} ({score(text, LINES[best]):.2f})  heard: {text[:70]}")
        if best in found:
            print(f"   WARNING: {best} matched twice; keeping the closer match")
            if score(text, LINES[best]) <= found[best][1]:
                continue
        found[best] = (mp3, score(text, LINES[best]))
    for k, (mp3, _) in found.items():
        open(f"{OUT}/{k}.mp3", "wb").write(mp3)
    print("missing:", [k for k in LINES if k not in found] or "none")


asyncio.run(main(sys.argv[1:]))
