# ReplyFlow x VoxCPM2 on Modal (always on, uses Modal's free monthly credit).
# Run inside any Colab notebook (no GPU needed) with:
#   B="https://<your-replyflow-site>"; import urllib.request as u; exec(u.urlopen(B+"/voxcpm/modal_setup.py").read())
import os, re, secrets, subprocess, sys, urllib.request

BASE = globals().get("B", "").rstrip("/")
if not BASE:
    raise SystemExit("Set B to your ReplyFlow address first, e.g. B='https://your-site.com'")


def say(msg):
    print(msg, flush=True)


def run_live(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = []
    for line in p.stdout:
        out.append(line)
        say("     " + line.rstrip())
    p.wait()
    return p.returncode, "".join(out)


say("1/4  Installing Modal…")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "modal"], check=True)
os.makedirs("replyflow_modal", exist_ok=True)
os.chdir("replyflow_modal")
for f in ("voxcpm_server.py", "modal_voxcpm.py"):
    urllib.request.urlretrieve(f"{BASE}/voxcpm/{f}", f)

say("2/4  Sign in to Modal: open the link below, approve, then come back here.")
code, _ = run_live(["modal", "token", "new"])
if code:
    raise SystemExit("Modal sign-in failed. Run the cell again.")

say("3/4  Saving a private API key in Modal…")
key = secrets.token_urlsafe(24)
code, out = run_live(["modal", "secret", "create", "replyflow-voxcpm", f"VOXCPM_API_KEY={key}", "--force"])
if code:
    raise SystemExit("Could not save the secret:\n" + out[-1500:])

say("4/4  Deploying VoxCPM2 to Modal (first time 3-6 minutes)…")
code, out = run_live(["modal", "deploy", "modal_voxcpm.py"])
m = re.search(r"https://[^\s]+\.modal\.run", out)
if code or not m:
    raise SystemExit("Deploy failed:\n" + out[-2500:])

say("\n" + "=" * 64)
say("  VoxCPM2 is deployed on Modal. Paste these into ReplyFlow:")
say("  AI Settings -> Voice -> VoxCPM2, then Save and press 'Test Khmer voice'\n")
say(f"  Server URL : {m.group(0)}")
say(f"  API key    : {key}")
say("=" * 64)
say("It sleeps when idle (no cost) and wakes on the next voice message.")
say("The very first voice after a quiet period can take 30-90 seconds; then it is fast.")
say("You can close this notebook now.")
