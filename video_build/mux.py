"""Muxes the recorded tour with the Khmer narration into public/videos/replyflow-tour.mp4 (+ poster)."""
import json
import subprocess

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
T = json.load(open("/app/video_build/timeline.json"))
OUT = "/app/frontend/public/videos"
LEAD = 0.3

inputs, filters = ["-i", T["video"]], []
for i, s in enumerate(T["starts"]):
    inputs += ["-i", f"/app/video_build/audio/{i:02d}.mp3"]
    ms = int((s + LEAD) * 1000)
    filters.append(f"[{i + 1}:a]adelay={ms}|{ms},volume=1.6[a{i}]")
mix = "".join(f"[a{i}]" for i in range(len(T["starts"])))
filters.append(f"{mix}amix=inputs={len(T['starts'])}:normalize=0,apad[aout]")
subprocess.run([FF, "-y", *inputs, "-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                "-c:a", "aac", "-b:a", "128k", "-shortest", f"{OUT}/replyflow-tour.mp4"], check=True)
subprocess.run([FF, "-y", "-ss", "4", "-i", f"{OUT}/replyflow-tour.mp4", "-frames:v", "1", "-q:v", "4", f"{OUT}/replyflow-tour.jpg"], check=True)
print("ok")
