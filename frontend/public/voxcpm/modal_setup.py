# ReplyFlow x VoxCPM2 on Modal (always on, uses Modal's free monthly credit).
# Copy the Modal line from ReplyFlow (AI Settings -> Voice -> Advanced) and run it in any Colab notebook (no GPU needed).
import json, os, re, secrets, subprocess, sys, time, urllib.error, urllib.request

BASE = globals().get("B", "").rstrip("/")
TOKEN = globals().get("T", "")
if not BASE:
    raise SystemExit("Set B to your ReplyFlow address first, e.g. B='https://your-site.com'")


def say(msg):
    print(msg, flush=True)


def report(stage, **kw):
    if not TOKEN:
        return True, ""
    data = json.dumps({"stage": stage, "source": "modal", **kw}).encode()
    req = urllib.request.Request(f"{BASE}/api/voice/voxcpm-pair/{TOKEN}", data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=120)
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


def run_live(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = []
    for line in p.stdout:
        out.append(line)
        say("     " + line.rstrip())
    p.wait()
    return p.returncode, "".join(out)


report("installing")
say("1/4  Installing Modal…")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "modal"], check=True)
os.makedirs("replyflow_modal", exist_ok=True)
os.chdir("replyflow_modal")
for f in ("voxcpm_server.py", "modal_voxcpm.py"):
    urllib.request.urlretrieve(f"{BASE}/voxcpm/{f}", f)

say("2/4  Sign in to Modal: open the link below, approve, then come back here.")
code, _ = run_live(["modal", "token", "new"])
if code:
    fail("Modal sign-in failed. Press ▶ again.")

say("3/4  Saving a private API key in Modal…")
key = secrets.token_urlsafe(24)
code, out = run_live(["modal", "secret", "create", "replyflow-voxcpm", f"VOXCPM_API_KEY={key}", "--force"])
if code:
    fail("Could not save the secret:\n" + out[-1500:])

report("loading")
say("4/4  Deploying VoxCPM2 to Modal (first time 3-6 minutes)…")
code, out = run_live(["modal", "deploy", "modal_voxcpm.py"])
m = re.search(r"https://[^\s]+\.modal\.run", out)
if code or not m:
    fail("Deploy failed:\n" + out[-2500:])
url = m.group(0)

report("linking")
say("     Waking up the server and connecting to ReplyFlow (up to 3 minutes)…")
ok, err = False, ""
for _ in range(4):
    ok, err = report("ready", url=url, key=key)
    if ok:
        break
    time.sleep(15)

say("\n" + "=" * 64)
if TOKEN and ok:
    say("  ✅ CONNECTED! Go back to ReplyFlow — everything is saved automatically.")
    say("  ✅ បានភ្ជាប់រួចរាល់! ត្រឡប់ទៅ ReplyFlow វិញ — អ្វីៗត្រូវបានរក្សាទុកដោយស្វ័យប្រវត្តិ។")
else:
    if TOKEN:
        say(f"  Could not connect automatically ({err}). Paste these into ReplyFlow -> Advanced:")
    else:
        say("  VoxCPM2 is deployed on Modal. Paste these into ReplyFlow -> AI Settings -> Voice -> Advanced:")
    say(f"  Server URL : {url}")
    say(f"  API key    : {key}")
say("=" * 64)
say("It sleeps when idle (no cost) and wakes on the next voice message (first one can take 30-90 s).")
say("You can close this notebook now.")
