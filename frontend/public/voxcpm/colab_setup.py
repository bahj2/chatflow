# ReplyFlow x VoxCPM2 on Google Colab (free T4 GPU).
# Run inside Colab with:  B="https://<your-replyflow-site>"; import urllib.request as u; exec(u.urlopen(B+"/voxcpm/colab_setup.py").read())
import os, re, secrets, subprocess, sys, threading, time, urllib.request

BASE = globals().get("B", "").rstrip("/")
if not BASE:
    raise SystemExit("Set B to your ReplyFlow address first, e.g. B='https://your-site.com'")


def say(msg):
    print(msg, flush=True)


say("1/4  Checking GPU…")
gpu = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True).stdout if os.path.exists("/usr/bin/nvidia-smi") else ""
if "GPU" not in gpu:
    raise SystemExit("No GPU found. In Colab click: Runtime -> Change runtime type -> T4 GPU -> Save. Then run this cell again.")
say("     " + gpu.strip())

say("2/4  Installing VoxCPM2 (2-4 minutes)…")
r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "voxcpm", "fastapi", "uvicorn", "soundfile"], capture_output=True, text=True)
if r.returncode:
    raise SystemExit("Install failed:\n" + r.stderr[-2000:])
if not os.path.exists("cloudflared"):
    urllib.request.urlretrieve("https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", "cloudflared")
    os.chmod("cloudflared", 0o755)
urllib.request.urlretrieve(BASE + "/voxcpm/voxcpm_server.py", "voxcpm_server.py")

key = secrets.token_urlsafe(24)
say("3/4  Loading the VoxCPM2 model (first run downloads ~5 GB, 2-6 minutes)…")
log = open("voxcpm_server.log", "w")
srv = subprocess.Popen([sys.executable, "voxcpm_server.py"], env={**os.environ, "VOXCPM_API_KEY": key, "PORT": "8000"}, stdout=log, stderr=subprocess.STDOUT)
start = time.time()
while True:
    if srv.poll() is not None:
        raise SystemExit("Server stopped:\n" + open("voxcpm_server.log").read()[-3000:])
    try:
        req = urllib.request.Request("http://localhost:8000/health", headers={"Authorization": f"Bearer {key}"})
        if urllib.request.urlopen(req, timeout=5).status == 200:
            break
    except Exception:
        pass
    if time.time() - start > 1200:
        raise SystemExit("Model took too long to load. Check voxcpm_server.log")
    time.sleep(5)
say(f"     Model ready in {int(time.time() - start)} s")

say("4/4  Opening a free public link (Cloudflare)…")
tun = subprocess.Popen(["./cloudflared", "tunnel", "--url", "http://localhost:8000", "--no-autoupdate"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
url = None
for line in tun.stdout:
    m = re.search(r"https://[-a-z0-9]+\.trycloudflare\.com", line)
    if m:
        url = m.group(0)
        break
threading.Thread(target=lambda: [None for _ in tun.stdout], daemon=True).start()
if not url:
    raise SystemExit("Could not open the public link. Run the cell again.")

say("\n" + "=" * 64)
say("  VoxCPM2 is running. Paste these into ReplyFlow:")
say("  AI Settings -> Voice -> VoxCPM2, then Save and press 'Test Khmer voice'\n")
say(f"  Server URL : {url}")
say(f"  API key    : {key}")
say("=" * 64)
say("Keep this browser tab open. If Colab stops, ReplyFlow automatically uses the Microsoft Khmer voice")
say("until you run this cell again (you will get a new link).")

while True:
    time.sleep(600)
    if srv.poll() is not None:
        say("Server stopped. Run the cell again.")
        break
    say(time.strftime("%H:%M") + "  still running")
