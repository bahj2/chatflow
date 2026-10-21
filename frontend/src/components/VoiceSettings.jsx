import { useState } from "react";
import { Play, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/auth";
import { mediaUrl } from "@/components/Attachments";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const VOICES = [["nova", "Nova — energetic"], ["shimmer", "Shimmer — bright"], ["coral", "Coral — warm"], ["alloy", "Alloy — neutral"], ["ash", "Ash — clear"],
  ["echo", "Echo — calm"], ["fable", "Fable — expressive"], ["onyx", "Onyx — deep"], ["sage", "Sage — measured"]];

const ENGINES = { "voxcpm2-hf": "VoxCPM2 · Hugging Face demo", openai: "OpenAI" };

const Preview = ({ text, label, testid, s }) => {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const run = async () => {
    setBusy(true);
    setErr("");
    try { setRes((await api.post("/voice/test", { text, voice: s.voice })).data); } catch (e) { setRes(null); setErr(errMsg(e)); toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="flex flex-wrap items-center gap-3">
      <button type="button" onClick={run} disabled={busy} data-testid={testid}
        className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold hover:bg-white/5 disabled:opacity-60">
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />} {busy ? "Generating…" : label}
      </button>
      {res && <><audio controls autoPlay src={mediaUrl(res.media_id)} className="h-9" data-testid={`${testid}-audio`} />
        <span className="text-[11px] font-mono text-slate-500" data-testid={`${testid}-engine`}>engine: {ENGINES[res.engine] || res.engine}</span></>}
      {err && <span className="w-full text-xs text-amber-300" data-testid={`${testid}-error`}>{err}</span>}
    </div>
  );
};

export const VoiceSection = ({ s, setS, Section, Field }) => (
  <Section title="Voice" desc="Customers can send voice messages. The AI understands them (incl. Khmer) and answers with voice.">
    <div className="flex items-center justify-between rounded-xl border border-white/10 bg-[#0F1522] p-4">
      <div><p className="font-medium text-sm">Reply with voice to voice messages</p><p className="text-xs text-slate-400">Typed messages always get text replies.</p></div>
      <Switch checked={s.voice_replies} onCheckedChange={(v) => setS((x) => ({ ...x, voice_replies: v }))} data-testid="voice-replies-switch" />
    </div>
    <Field label="AI voice (English and other languages)">
      <Select value={s.voice} onValueChange={(v) => setS((x) => ({ ...x, voice: v }))}>
        <SelectTrigger data-testid="voice-select"><SelectValue /></SelectTrigger>
        <SelectContent>{VOICES.map(([v, l]) => <SelectItem key={v} value={v} data-testid={`voice-select-${v}`}>{l}</SelectItem>)}</SelectContent>
      </Select>
    </Field>
    <Preview s={s} text="Hi! Thanks for your message. How can I help you today?" label="Preview voice" testid="voice-preview-btn" />

    <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.04] p-4 space-y-3" data-testid="khmer-voice-card">
      <div>
        <p className="font-medium text-sm">Khmer voice — VoxCPM2</p>
        <p className="text-xs text-slate-400 mt-1 leading-relaxed">
          Khmer replies are spoken by VoxCPM2 through its free official Hugging Face demo, with a warm, friendly young woman’s voice.
          If the demo is busy or down (no answer within 45 seconds), customers get the reply as text instead.
        </p>
      </div>
      <Preview s={s} text="សួស្តីបង! អរគុណដែលបានទាក់ទងមកហាងយើងខ្ញុំ។ តើខ្ញុំអាចជួយអ្វីបានដែរ?" label="Test Khmer voice" testid="khmer-preview-btn" />
    </div>
  </Section>
);
