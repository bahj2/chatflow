"""Render /demo?video=1 into a vertical 1080x1920 MP4 with narrator + chat voice clips.

Clips: {voice}/{n1..n5,c1,c2}.mp3  (n = narrator, c1 = customer voice note, c2 = AI voice note)
Usage: python3 scripts/make_demo_video.py [voice=DIR] [out=FILE] [base=http://localhost:3000]
Defaults: voice=/app/frontend/public/demo/voice, out=/app/frontend/public/demo/replyflow-demo.mp4
"""
import asyncio
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import imageio_ffmpeg
from playwright.async_api import async_playwright

FF = imageio_ffmpeg.get_ffmpeg_exe()
DEMO = "/app/frontend/public/demo"
ARGS = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
VOICE = ARGS.get("voice", f"{DEMO}/voice")
CLIPS = ["n1", "n2", "n3", "n4", "n5", "c1", "c2"]
OUT = ARGS.get("out", f"{DEMO}/replyflow-demo.mp4")
BASE = ARGS.get("base", "http://localhost:3000")


def duration(path: str) -> float:
    err = subprocess.run([FF, "-i", path], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def write_timeline() -> dict:
    missing = [c for c in CLIPS if not os.path.exists(f"{VOICE}/{c}.mp3")]
    if missing:
        raise SystemExit(f"Missing voice clips: {missing} in {VOICE}")
    tl = {c: round(duration(f"{VOICE}/{c}.mp3"), 2) for c in CLIPS}
    json.dump(tl, open(f"{DEMO}/voice/timeline.json", "w"))
    print("timeline", tl)
    return tl


async def record(tmp: str) -> tuple:
    frames, cues = [], {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=shutil.which("google-chrome") or "/usr/bin/google-chrome", args=["--no-sandbox"])
        page = await (await browser.new_context(viewport={"width": 1080, "height": 1920})).new_page()
        done = asyncio.Event()

        def on_console(msg):
            m = re.match(r"CUE (\S+) (\d+)", msg.text)
            if m:
                cues[m.group(1)] = int(m.group(2)) / 1000
                if m.group(1) == "DONE":
                    done.set()
        page.on("console", on_console)
        cdp = await page.context.new_cdp_session(page)

        async def on_frame(ev):
            path = f"{tmp}/f{len(frames):05d}.jpg"
            open(path, "wb").write(base64.b64decode(ev["data"]))
            frames.append((ev["metadata"]["timestamp"], path))
            await cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
        cdp.on("Page.screencastFrame", lambda ev: asyncio.ensure_future(on_frame(ev)))
        await page.goto(f"{BASE}/demo?video=1", wait_until="networkidle")
        await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": 1080, "maxHeight": 1920, "everyNthFrame": 1})
        await asyncio.wait_for(done.wait(), timeout=240)
        await asyncio.sleep(0.5)
        await cdp.send("Page.stopScreencast")
        await browser.close()
    return frames, cues


def build(frames: list, cues: dict, tmp: str):
    t0, t1 = cues["START"], cues["DONE"]
    frames = sorted(frames)
    first = max([f for f in frames if f[0] <= t0] or frames[:1])
    use = [first] + [f for f in frames if t0 < f[0] <= t1]
    lines = []
    for i, (ts, path) in enumerate(use):
        start = max(ts, t0)
        end = use[i + 1][0] if i + 1 < len(use) else t1
        lines += [f"file '{path}'", f"duration {max(end - start, 0.001):.3f}"]
    lines.append(f"file '{use[-1][1]}'")
    open(f"{tmp}/frames.txt", "w").write("\n".join(lines))
    inputs, filters, labels = [], [], []
    for i, c in enumerate([c for c in CLIPS if c in cues]):
        delay = int((cues[c] - t0) * 1000)
        inputs += ["-i", f"{VOICE}/{c}.mp3"]
        filters.append(f"[{i + 1}:a]aresample=44100,adelay={delay}|{delay}[a{i}]")
        labels.append(f"[a{i}]")
    graph = ";".join(filters) + f";{''.join(labels)}amix=inputs={len(labels)}:normalize=0,apad[aout]"
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{tmp}/frames.txt", *inputs,
                    "-filter_complex", graph, "-map", "0:v", "-map", "[aout]", "-shortest",
                    "-vf", "fps=30,scale=1080:1920:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", OUT], check=True)
    print("video", OUT, f"{t1 - t0:.1f}s", os.path.getsize(OUT) // 1024, "KB")


async def main():
    write_timeline()
    tmp = tempfile.mkdtemp()
    frames, cues = await record(tmp)
    print("frames", len(frames), "cues", {k: round(v - cues["START"], 2) for k, v in cues.items()})
    build(frames, cues, tmp)
    shutil.rmtree(tmp)


asyncio.run(main())
