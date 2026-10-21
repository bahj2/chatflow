import { useRef, useState } from "react";
import { Play, Loader2, Mic, Square, Upload } from "lucide-react";
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

const Preview = ({ text, label, testid }) => {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const run = async () => {
    setBusy(true);
    try { setRes((await api.post("/voice/test", { text })).data); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="flex flex-wrap items-center gap-3">
      <button type="button" onClick={run} disabled={busy} data-testid={testid}
        className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold hover:bg-white/5 disabled:opacity-60">
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />} {label}
      </button>
      {res && <><audio controls autoPlay src={mediaUrl(res.media_id)} className="h-9" data-testid={`${testid}-audio`} />
        <span className="text-[11px] font-mono text-slate-500" data-testid={`${testid}-engine`}>engine: {res.engine === "voxcpm2" ? "VoxCPM2 (seller voice)" : "OpenAI"}</span></>}
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
        {s.seller_voice_media_id && <audio controls src={mediaUrl(s.seller_voice_media_id)} className="h-9" data-testid="seller-voice-audio" />}
      </div>
      {s.seller_voice_media_id && (
        <label className="block"><span className="text-xs text-slate-400 mb-1.5 block">Exact words spoken in the sample (filled in automatically — fix any mistakes, then Save)</span>
          <Textarea rows={2} value={s.seller_voice_text} onChange={(e) => setS((x) => ({ ...x, seller_voice_text: e.target.value }))} data-testid="seller-voice-text" />
        </label>
      )}
    </div>
  );
};

export const VoiceSection = ({ s, setS, Section, Field }) => (
  <Section title="Voice" desc="Customers can send voice messages. The AI understands them (50+ languages incl. Khmer) and answers with voice.">
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
    <Preview text="Hi! Thanks for your message. How can I help you today?" label="Preview voice (save first)" testid="voice-preview-btn" />

    <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.04] p-4 space-y-4" data-testid="khmer-voice-card">
      <div>
        <p className="font-medium text-sm">Khmer voice in the seller’s own voice — VoxCPM2</p>
        <p className="text-xs text-slate-400 mt-1">VoxCPM2 runs on your own GPU server (e.g. <code className="font-mono">vllm serve openbmb/VoxCPM2 --omni</code>). Paste its address here. Without it, Khmer replies use the OpenAI voice above (English accent).</p>
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <Field label="VoxCPM2 server URL"><Input value={s.voxcpm_url} onChange={(e) => setS((x) => ({ ...x, voxcpm_url: e.target.value }))} placeholder="https://my-gpu-server.com:8000" data-testid="voxcpm-url-input" /></Field>
        <Field label="API key (optional)"><Input type="password" value={s.voxcpm_key} onChange={(e) => setS((x) => ({ ...x, voxcpm_key: e.target.value }))} data-testid="voxcpm-key-input" /></Field>
      </div>
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
      <Preview text="សួស្តី! អរគុណសម្រាប់សាររបស់អ្នក។ តើខ្ញុំអាចជួយអ្វីបាន?" label="Test Khmer voice (save first)" testid="khmer-preview-btn" />
    </div>
  </Section>
);
