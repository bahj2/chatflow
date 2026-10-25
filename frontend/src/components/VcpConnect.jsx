import { useState } from "react";
import { Link2, Loader2, Play, RefreshCw, Unplug, Copy, CheckCircle2, Monitor } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/auth";
import { mediaUrl } from "@/components/Attachments";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const TUNNEL = "cloudflared tunnel --url http://localhost:8100";
const CLOUDFLARED = "https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/";
const TEST_KM = "សួស្តីបង! អរគុណដែលបានទាក់ទងមកហាងយើងខ្ញុំ។ តើបងចង់កុម្ម៉ង់អ្វីដែរថ្ងៃនេះ?";
const DEFAULT = "__default";
const btn = "inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold disabled:opacity-50";

const toSettings = (d) => ({ vcp_url: d.url, vcp_model: d.model, vcp_voice_id: d.voice_id, vcp_voices: d.voices });

const Steps = () => (
  <ol className="list-decimal pl-4 space-y-1.5 text-xs text-slate-400 leading-relaxed" data-testid="vcp-steps">
    <li>On your computer, open <b className="text-slate-200">Voice Creator Pro</b> → Settings (gear) → turn on <b className="text-slate-200">Enable HTTP API</b> (port 8100) and set an <b className="text-slate-200">API key</b>.</li>
    <li>Choose <b className="text-slate-200">VoxCPM2</b> as the model. Optional: clone your voice there and save it.</li>
    <li>Install Cloudflare’s free <a href={CLOUDFLARED} target="_blank" rel="noreferrer" className="text-emerald-400 underline" data-testid="vcp-cloudflared-link">cloudflared</a> and run:
      <span className="mt-1 flex items-center gap-2">
        <code className="rounded bg-black/40 px-2 py-1 font-mono text-[11px] text-slate-200" data-testid="vcp-tunnel-command">{TUNNEL}</code>
        <button type="button" onClick={() => navigator.clipboard.writeText(TUNNEL).then(() => toast.success("Copied"))} className="text-slate-400 hover:text-white" data-testid="vcp-copy-command-btn"><Copy className="h-3.5 w-3.5" /></button>
      </span>
      It shows a link like https://….trycloudflare.com — copy it.</li>
    <li>Paste the link and the API key below and press Connect. Keep the computer awake with the app and the tunnel open.</li>
  </ol>
);

const ConnectForm = ({ setS }) => {
  const [url, setUrl] = useState("");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const go = async () => {
    setBusy(true);
    setErr("");
    try { const { data } = await api.post("/voice/vcp/connect", { url, key }); setS((x) => ({ ...x, ...toSettings(data) })); toast.success("Voice Creator Pro connected"); }
    catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-2">
      <div className="grid gap-2 sm:grid-cols-[1fr_190px_auto]">
        <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://xxxx.trycloudflare.com" data-testid="vcp-url-input" />
        <Input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="API key" data-testid="vcp-key-input" />
        <button type="button" onClick={go} disabled={busy || !url.trim() || !key.trim()} data-testid="vcp-connect-btn" className={`${btn} justify-center bg-emerald-500 text-slate-950 hover:bg-emerald-400`}>
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Link2 className="h-3.5 w-3.5" />} {busy ? "Connecting…" : "Connect"}
        </button>
      </div>
      {err && <p className="text-xs text-amber-300" data-testid="vcp-error">{err}</p>}
    </div>
  );
};

const VoicePick = ({ s, setS }) => {
  const pick = async (v) => {
    try { const { data } = await api.put("/voice/vcp/voice", { voice_id: v === DEFAULT ? "" : v }); setS((x) => ({ ...x, ...toSettings(data) })); toast.success("Voice saved"); }
    catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <label className="block"><span className="text-xs text-slate-400 mb-1.5 block">Voice used for Khmer replies</span>
      <Select value={s.vcp_voice_id || DEFAULT} onValueChange={pick}>
        <SelectTrigger data-testid="vcp-voice-select"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value={DEFAULT} data-testid="vcp-voice-option-default">Seller sample below (or default young woman voice)</SelectItem>
          {s.vcp_voices.map((v) => <SelectItem key={v.id} value={v.id} data-testid={`vcp-voice-option-${v.id}`}>{v.name}</SelectItem>)}
        </SelectContent>
      </Select>
    </label>
  );
};

const TestVcp = () => {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const run = async () => {
    setBusy(true);
    setErr("");
    try { setRes((await api.post("/voice/test", { text: TEST_KM, only_vcp: true })).data); }
    catch (e) { setRes(null); setErr(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="flex flex-wrap items-center gap-3">
      <button type="button" onClick={run} disabled={busy} data-testid="vcp-test-btn" className={`${btn} border border-white/10 hover:bg-white/5`}>
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />} {busy ? "Generating on your computer…" : "Test Voice Creator Pro"}
      </button>
      {res && <audio controls autoPlay src={mediaUrl(res.media_id)} className="h-9" data-testid="vcp-test-audio" />}
      {err && <span className="w-full text-xs text-amber-300" data-testid="vcp-test-error">{err}</span>}
    </div>
  );
};

const Connected = ({ s, setS }) => {
  const [busy, setBusy] = useState("");
  const act = async (kind) => {
    setBusy(kind);
    try {
      const { data } = kind === "refresh" ? await api.post("/voice/vcp/refresh") : await api.delete("/voice/vcp");
      setS((x) => ({ ...x, ...toSettings(data) }));
      toast.success(kind === "refresh" ? "Voices reloaded" : "Voice Creator Pro disconnected");
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  return (
    <div className="space-y-3" data-testid="vcp-connected">
      <p className="flex flex-wrap items-center gap-1.5 text-xs text-emerald-400" data-testid="vcp-status">
        <CheckCircle2 className="h-3.5 w-3.5" /> Connected · <span className="font-mono text-slate-300 break-all">{s.vcp_url}</span>
        <span className="text-slate-500">· model: {s.vcp_model || "the one selected in the app"}</span>
      </p>
      <VoicePick s={s} setS={setS} />
      <div className="flex flex-wrap items-center gap-2">
        <TestVcp />
        <button type="button" onClick={() => act("refresh")} disabled={!!busy} data-testid="vcp-refresh-btn" className={`${btn} border border-white/10 hover:bg-white/5`}>
          {busy === "refresh" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />} Refresh voices
        </button>
        <button type="button" onClick={() => act("disconnect")} disabled={!!busy} data-testid="vcp-disconnect-btn" className={`${btn} border border-white/10 text-slate-400 hover:text-red-300`}>
          <Unplug className="h-3.5 w-3.5" /> Disconnect
        </button>
      </div>
    </div>
  );
};

export const VcpConnect = ({ s, setS }) => (
  <div className="space-y-3 border-t border-white/10 pt-4" data-testid="vcp-section">
    <div>
      <p className="font-medium text-sm flex items-center gap-1.5"><Monitor className="h-4 w-4 text-amber-300" /> Voice Creator Pro on your computer (optional)</p>
      <p className="text-xs text-slate-400 mt-1 leading-relaxed">Use VoxCPM2 from your own Voice Creator Pro desktop app. ReplyFlow tries it first. If your computer is off, it uses the free Hugging Face demo, and then text.</p>
    </div>
    {s.vcp_url ? <Connected s={s} setS={setS} /> : <><Steps /><ConnectForm setS={setS} /></>}
  </div>
);
