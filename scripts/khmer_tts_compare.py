import asyncio, os, sys, tempfile, uuid, difflib, time
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import edge_tts
import media as M
from emergentintegrations.llm.openai import OpenAITextToSpeech
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
KEY = os.environ["EMERGENT_LLM_KEY"]
TEXTS = ["សួស្តីបង! យើងមានលក់កាបូបស្បែក តម្លៃចាប់ពី ២៥ ដុល្លារ។ តើបងចង់មើលម៉ូដណាដែរ?",
         "ហាងយើងបើកពីម៉ោង ៨ ព្រឹក ដល់ម៉ោង ៨ យប់ រៀងរាល់ថ្ងៃ។ អរគុណច្រើនបង!"]

async def transcribe(mp3):
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(mp3); p = f.name
    chat = LlmChat(api_key=KEY, session_id=str(uuid.uuid4()), system_message="You are an expert Khmer speech transcriber.").with_model("gemini", "gemini-3-flash-preview")
    return (await chat.send_message(UserMessage(text="Transcribe this audio exactly in Khmer script. Output only the transcript.",
                                                 file_contents=[FileContentWithMimeType(file_path=p, mime_type="audio/mpeg")]))).strip()

def norm(t):
    return "".join(ch for ch in t if "\u1780" <= ch <= "\u17ff")

async def edge(text, voice):
    out = b""
    async for c in edge_tts.Communicate(text, voice).stream():
        if c["type"] == "audio":
            out += c["data"]
    return out

async def oai(text, model, **kw):
    return await OpenAITextToSpeech(api_key=KEY).generate_speech(text=text, model=model, voice="nova", **kw)

async def main():
    engines = {
        "openai tts-1": lambda t: oai(t, "tts-1"),
        "openai gpt-4o-mini-tts": lambda t: oai(t, "gpt-4o-mini-tts", instructions="Speak natural, native Cambodian Khmer with clear Phnom Penh pronunciation."),
        "edge km-KH-SreymomNeural": lambda t: edge(t, "km-KH-SreymomNeural"),
        "edge km-KH-PisethNeural": lambda t: edge(t, "km-KH-PisethNeural"),
    }
    for name, fn in engines.items():
        scores, secs = [], []
        for t in TEXTS:
            try:
                t0 = time.perf_counter(); audio = await fn(t); secs.append(time.perf_counter() - t0)
                back = await transcribe(audio)
                scores.append(difflib.SequenceMatcher(None, norm(t), norm(back)).ratio())
                last = back
            except Exception as e:
                print(f"{name:28s} ERROR {str(e)[:120]}"); break
        if scores:
            print(f"{name:28s} clarity {sum(scores)/len(scores)*100:5.1f}%  gen {sum(secs)/len(secs):.1f}s  heard: {last[:70]}")

asyncio.run(main())
