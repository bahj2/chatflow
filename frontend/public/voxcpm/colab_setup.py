# ReplyFlow x VoxCPM2 on Google Colab (free T4 GPU).
# Copy the line from ReplyFlow (AI Settings -> Voice) and run it in Colab. It connects to ReplyFlow by itself.
import json, os, re, secrets, shutil, subprocess, sys, threading, time, urllib.error, urllib.request

BASE = globals().get("B", "").rstrip("/")
TOKEN = globals().get("T", "")
if not BASE:
    raise SystemExit("Set B to your ReplyFlow address first, e.g. B='https://your-site.com'")


def say(msg):
    print(msg, flush=True)


def report(stage, **kw):
    if not TOKEN:
        return True, ""
    data = json.dumps({"stage": stage, "source": "colab", **kw}).encode()
    req = urllib.request.Request(f"{BASE}/api/voice/voxcpm-pair/{TOKEN}", data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=60)
        return True, ""
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read()).get("detail", str(e))
        except Exception:
            return False, str(e)
    except Exception as e:
        return False, str(e)


def fail(msg):
    report("error", error=msg[-480:])
    raise SystemExit(msg)


report("started")
say("1/4  Checking GPU…   (ពិនិត្យ GPU)")
smi = shutil.which("nvidia-smi")
gpu = subprocess.run([smi, "-L"], capture_output=True, text=True).stdout if smi else ""
if "GPU" not in gpu:
    report("no_gpu")
    raise SystemExit("No GPU. Click: Runtime -> Change runtime type -> T4 GPU -> Save. Then press ▶ again.\n"
                     "មិនមាន GPU។ ចុច Runtime -> Change runtime type -> T4 GPU -> Save រួចចុច ▶ ម្ដងទៀត។")
say("     " + gpu.strip())

report("installing")
say("2/4  Installing VoxCPM2 (2-4 minutes)…   (កំពុងដំឡើង)")
r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "voxcpm", "fastapi", "uvicorn", "soundfile"], capture_output=True, text=True)
if r.returncode:
    fail("Install failed:\n" + r.stderr[-2000:])
if not os.path.exists("cloudflared"):
    urllib.request.urlretrieve("https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", "cloudflared")
    os.chmod("cloudflared", 0o755)
urllib.request.urlretrieve(BASE + "/voxcpm/voxcpm_server.py", "voxcpm_server.py")

key = secrets.token_urlsafe(24)
auth = {"Authorization": f"Bearer {key}"}
report("loading")
say("3/4  Loading the voice model (first run downloads ~5 GB, 2-6 minutes)…   (កំពុងផ្ទុកម៉ូដែល)")
log = open("voxcpm_server.log", "w")
srv = subprocess.Popen([sys.executable, "voxcpm_server.py"], env={**os.environ, "VOXCPM_API_KEY": key, "PORT": "8000"}, stdout=log, stderr=subprocess.STDOUT)
start = time.time()
while True:
    if srv.poll() is not None:
        fail("Server stopped:\n" + open("voxcpm_server.log").read()[-3000:])
    try:
        if urllib.request.urlopen(urllib.request.Request("http://localhost:8000/health", headers=auth), timeout=5).status == 200:
            break
    except Exception:
        pass
    if time.time() - start > 1200:
        fail("Model took too long to load. Press ▶ again.")
    time.sleep(5)
say(f"     Model ready in {int(time.time() - start)} s")

report("linking")
say("4/4  Opening a free public link and connecting to ReplyFlow…   (កំពុងភ្ជាប់)")
tun = subprocess.Popen(["./cloudflared", "tunnel", "--url", "http://localhost:8000", "--no-autoupdate"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
url = None
for line in tun.stdout:
    m = re.search(r"https://[-a-z0-9]+\.trycloudflare\.com", line)
    if m:
        url = m.group(0)
        break
threading.Thread(target=lambda: [None for _ in tun.stdout], daemon=True).start()
if not url:
    fail("Could not open the public link. Press ▶ again.")

for _ in range(30):
    try:
        if urllib.request.urlopen(urllib.request.Request(url + "/health", headers=auth), timeout=10).status == 200:
            break
    except Exception:
        time.sleep(4)

ok, err = False, ""
for _ in range(6):
    ok, err = report("ready", url=url, key=key)
    if ok:
        break
    time.sleep(10)

say("\n" + "=" * 64)
if TOKEN and ok:
    say("  ✅ CONNECTED! Go back to ReplyFlow — everything is saved automatically.")
    say("  ✅ បានភ្ជាប់រួចរាល់! ត្រឡប់ទៅ ReplyFlow វិញ — អ្វីៗត្រូវបានរក្សាទុកដោយស្វ័យប្រវត្តិ។")
else:
    if TOKEN:
        say(f"  Could not connect automatically ({err}). Paste these into ReplyFlow -> Advanced:")
    else:
        say("  VoxCPM2 is running. Paste these into ReplyFlow -> AI Settings -> Voice -> Advanced:")
    say(f"  Server URL : {url}")
    say(f"  API key    : {key}")
say("=" * 64)
say("Keep this tab open. Colab stops after ~12 hours — then just press ▶ again.")
say("សូមទុកផ្ទាំងនេះឲ្យបើក។ Colab ឈប់ក្រោយប្រហែល ១២ ម៉ោង — ពេលនោះគ្រាន់តែចុច ▶ ម្ដងទៀត។")

while True:
    time.sleep(300)
    if srv.poll() is not None:
        report("error", error="Server stopped. Press ▶ in Colab again.")
        say("Server stopped. Press ▶ again.")
        break
    report("alive")
    say(time.strftime("%H:%M") + "  still running")
