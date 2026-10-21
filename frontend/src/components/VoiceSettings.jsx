import { useRef, useState } from "react";
import { Play, Loader2, Mic, Square, Upload, Copy, CheckCircle2, XCircle, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/auth";
import { mediaUrl } from "@/components/Attachments";
import { useRecorder, blobName, clock } from "@/lib/recorder";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const VOICES = [["nova", "Nova — energetic"], ["shimmer", "Shimmer — bright"], ["coral", "Coral — warm"], ["alloy", "Alloy — neutral"], ["ash", "Ash — clear"],
  ["echo", "Echo — calm"], ["fable", "Fable — expressive"], ["onyx", "Onyx — deep"], ["sage", "Sage — measured"]];

const ENGINES = { voxcpm2: "VoxCPM2 (seller voice)", microsoft: "Microsoft native Khmer voice", "openai-hd": "OpenAI gpt-4o-mini-tts", openai: "OpenAI" };

const Preview = ({ text, label, testid, s }) => {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const run = async () => {
    setBusy(true);
    try { setRes((await api.post("/voice/test", { text, voice: s.voice, khmer_voice: s.khmer_voice })).data); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="flex flex-wrap items-center gap-3">
      <button type="button" onClick={run} disabled={busy} data-testid={testid}
        className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold hover:bg-white/5 disabled:opacity-60">
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />} {label}
      </button>
      {res && <><audio controls autoPlay src={mediaUrl(res.media_id)} className="h-9" data-testid={`${testid}-audio`} />
        <span className="text-[11px] font-mono text-slate-500" data-testid={`${testid}-engine`}>engine: {ENGINES[res.engine] || res.engine}</span>
        {res.vox_error && <span className="w-full text-xs text-amber-300" data-testid={`${testid}-vox-error`}>VoxCPM2 not used: {res.vox_error}</span>}</>}
    </div>
  );
};

const SellerVoice = ({ s, setS }) => {
  const rec = useRecorder();
  const fileRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const upload = async (blob, name) => {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", blob, name);
      fd.append("text", "");
      const { data } = await api.post("/settings/seller-voice", fd);
      setS((x) => ({ ...x, seller_voice_media_id: data.media_id, seller_voice_text: data.text }));
      toast.success("Seller voice saved");
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const toggleRec = async () => {
    if (!rec.recording) {
      try { await rec.start(); } catch { toast.error("Please allow microphone access"); }
      return;
    }
    const blob = await rec.stop();
    if (blob) upload(blob, blobName(blob));
  };
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={toggleRec} disabled={busy} data-testid="seller-voice-record-btn"
          className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold ${rec.recording ? "bg-red-500 text-white" : "border border-white/10 hover:bg-white/5"}`}>
          {rec.recording ? <><Square className="h-3.5 w-3.5" /> Stop {clock(rec.seconds)}</> : <><Mic className="h-3.5 w-3.5" /> Record 5–10 s</>}
        </button>
        <button type="button" onClick={() => fileRef.current?.click()} disabled={busy || rec.recording} data-testid="seller-voice-upload-btn"
          className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold hover:bg-white/5">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />} Upload audio
        </button>
        <input ref={fileRef} type="file" accept="audio/*" className="hidden" data-testid="seller-voice-input" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0], e.target.files[0].name)} />
        {s.seller_voice_media_id && <audio controls src={`${mediaUrl(s.seller_voice_media_id)}?auth=${localStorage.getItem("rf_token")}`} className="h-9" data-testid="seller-voice-audio" />}
      </div>
      {s.seller_voice_media_id && (
        <label className="block"><span className="text-xs text-slate-400 mb-1.5 block">Exact words spoken in the sample (filled in automatically — fix any mistakes, then Save)</span>
          <Textarea rows={2} value={s.seller_voice_text} onChange={(e) => setS((x) => ({ ...x, seller_voice_text: e.target.value }))} data-testid="seller-voice-text" />
        </label>
      )}
    </div>
  );
};

const copy = (t) => { navigator.clipboard.writeText(t); toast.success("Copied"); };

const CodeLine = ({ value, testid }) => (
  <div className="flex gap-2 min-w-0">
    <code className="flex-1 min-w-0 truncate rounded-lg bg-slate-950 border border-white/10 px-3 py-2 text-[11px] font-mono text-emerald-300" data-testid={testid}>{value}</code>
    <button type="button" onClick={() => copy(value)} data-testid={`${testid}-copy`} className="shrink-0 rounded-lg border border-white/10 px-3 hover:bg-white/5"><Copy className="h-4 w-4" /></button>
  </div>
);

const Guide = ({ title, badge, steps, line, testid }) => (
  <div className="rounded-xl border border-white/10 bg-[#0B0F17] p-4 space-y-3 min-w-0" data-testid={testid}>
    <p className="text-sm font-semibold flex items-center gap-2">{title}<span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 border border-emerald-500/30 rounded-full px-2 py-0.5">{badge}</span></p>
    <ol className="list-decimal pl-5 space-y-1.5 text-xs text-slate-300">{steps.map((st, i) => <li key={i}>{st}</li>)}</ol>
    <CodeLine value={line} testid={`${testid}-line`} />
  </div>
);

const SetupGuides = () => {
  const one = (file) => `B="${window.location.origin}"; import urllib.request as u; exec(u.urlopen(B+"/voxcpm/${file}").read())`;
  const colab = <a href="https://colab.research.google.com/#create=true" target="_blank" rel="noreferrer" className="text-emerald-400 inline-flex items-center gap-1">Google Colab <ExternalLink className="h-3 w-3" /></a>;
  return (
    <div className="grid lg:grid-cols-2 gap-3">
      <Guide title="Google Colab" badge="Free" testid="guide-colab" line={one("colab_setup.py")} steps={[
        <>Open {colab} and sign in with Google (a new notebook opens).</>,
        "Menu Runtime → Change runtime type → T4 GPU → Save.",
        "Paste the line below into the cell and press ▶. Wait ~5–8 minutes.",
        "Copy the Server URL + API key it shows into the fields below → Save → Test.",
        "Keep the tab open. The link changes each time Colab restarts (about every 12 h).",
      ]} />
      <Guide title="Modal" badge="Always on · $30 free / month" testid="guide-modal" line={one("modal_setup.py")} steps={[
        <>Create a free account at <a href="https://modal.com/signup" target="_blank" rel="noreferrer" className="text-emerald-400 inline-flex items-center gap-1">modal.com <ExternalLink className="h-3 w-3" /></a>.</>,
        <>Open {colab} (no GPU needed) and paste the line below, press ▶.</>,
        "Click the Modal sign-in link it prints and approve.",
        "When it finishes (~5 min) copy the Server URL + API key below → Save → Test.",
        "It sleeps when idle (no cost). First voice after a pause takes 30–90 s.",
      ]} />
    </div>
  );
};

const CheckConn = ({ s }) => {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const run = async () => {
    setBusy(true);
    try { setRes((await api.post("/voice/voxcpm-check", { url: s.voxcpm_url, key: s.voxcpm_key })).data); } catch (e) { setRes({ ok: false, error: errMsg(e) }); } finally { setBusy(false); }
  };
  return (
    <div className="flex flex-wrap items-center gap-3">
      <button type="button" onClick={run} disabled={busy || !s.voxcpm_url} data-testid="voxcpm-check-btn"
        className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold hover:bg-white/5 disabled:opacity-50">
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />} Check connection
      </button>
      {res && (res.ok
        ? <span className="text-xs text-emerald-400 flex items-center gap-1" data-testid="voxcpm-check-result"><CheckCircle2 className="h-3.5 w-3.5" /> Connected — VoxCPM2 on {res.gpu}</span>
        : <span className="text-xs text-red-400 flex items-center gap-1" data-testid="voxcpm-check-result"><XCircle className="h-3.5 w-3.5" /> {res.error}</span>)}
    </div>
  );
};

export const VoiceSection = ({ s, setS, Section, Field }) => (
  <Section title="Voice" desc="Customers can send voice messages. The AI understands them (incl. Khmer) and answers with voice.">
    <div className="flex items-center justify-between rounded-xl border border-white/10 bg-[#0F1522] p-4">
      <div><p className="font-medium text-sm">Reply with voice to voice messages</p><p className="text-xs text-slate-400">Typed messages always get text replies.</p></div>
      <Switch checked={s.voice_replies} onCheckedChange={(v) => setS((x) => ({ ...x, voice_replies: v }))} data-testid="voice-replies-switch" />
    </div>
    <div className="grid sm:grid-cols-[1fr_auto] gap-4 items-end">
      <Field label="AI voice">
        <Select value={s.voice} onValueChange={(v) => setS((x) => ({ ...x, voice: v }))}>
          <SelectTrigger data-testid="voice-select"><SelectValue /></SelectTrigger>
          <SelectContent>{VOICES.map(([v, l]) => <SelectItem key={v} value={v} data-testid={`voice-select-${v}`}>{l}</SelectItem>)}</SelectContent>
        </Select>
      </Field>
    </div>
    <Preview s={s} text="Hi! Thanks for your message. How can I help you today?" label="Preview voice" testid="voice-preview-btn" />

    <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.04] p-4 space-y-4" data-testid="khmer-voice-card">
      <div>
        <p className="font-medium text-sm">Khmer voice</p>
        <p className="text-xs text-slate-400 mt-1">Khmer replies are spoken by a native Khmer voice (Microsoft neural). Khmer voice messages from customers are understood by Gemini 3 Flash.</p>
      </div>
      <Field label="Native Khmer voice">
        <Select value={s.khmer_voice} onValueChange={(v) => setS((x) => ({ ...x, khmer_voice: v }))}>
          <SelectTrigger data-testid="khmer-voice-select"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="sreymom" data-testid="khmer-voice-sreymom">Sreymom — female</SelectItem>
            <SelectItem value="piseth" data-testid="khmer-voice-piseth">Piseth — male</SelectItem>
          </SelectContent>
        </Select>
      </Field>
      <Preview text="សួស្តីបង! អរគុណសម្រាប់សាររបស់បង។ តើខ្ញុំអាចជួយអ្វីបានដែរ?" label="Test Khmer voice (uses saved VoxCPM2 settings)" testid="khmer-preview-btn" s={s} />
      <div className="border-t border-white/10 pt-4">
        <p className="font-medium text-sm">Optional: seller’s own voice — VoxCPM2</p>
        <p className="text-xs text-slate-400 mt-1">VoxCPM2 needs a GPU server — use one of the free setups below (they run ReplyFlow’s VoxCPM2 server). It clones the seller’s voice from the sample. When set, it is used first; if it is off or fails, the native Khmer voice above is used automatically.</p>
      </div>
      <SetupGuides />
      <div className="grid sm:grid-cols-2 gap-4">
        <Field label="VoxCPM2 server URL"><Input value={s.voxcpm_url} onChange={(e) => setS((x) => ({ ...x, voxcpm_url: e.target.value }))} placeholder="https://xxxx.trycloudflare.com or https://xxxx.modal.run" data-testid="voxcpm-url-input" /></Field>
        <Field label="API key (optional)"><Input type="password" value={s.voxcpm_key} onChange={(e) => setS((x) => ({ ...x, voxcpm_key: e.target.value }))} data-testid="voxcpm-key-input" /></Field>
      </div>
      <CheckConn s={s} />
      <Field label="Use VoxCPM2 for">
        <Select value={s.voxcpm_for} onValueChange={(v) => setS((x) => ({ ...x, voxcpm_for: v }))}>
          <SelectTrigger data-testid="voxcpm-for-select"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="khmer" data-testid="voxcpm-for-khmer">Khmer replies only</SelectItem>
            <SelectItem value="all" data-testid="voxcpm-for-all">All voice replies (seller voice in every language)</SelectItem>
          </SelectContent>
        </Select>
      </Field>
      <Field label="Seller voice sample (clear, quiet room, 5–10 seconds)"><SellerVoice s={s} setS={setS} /></Field>
      <Preview s={s} text="សួស្តីបង! អរគុណដែលបានទាក់ទងមកហាងយើងខ្ញុំ។" label="Test seller voice (save first)" testid="voxcpm-preview-btn" />
    </div>
  </Section>
);
