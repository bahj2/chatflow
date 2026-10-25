import { useEffect, useRef, useState } from "react";
import { Play, Loader2, Mic, Square, Upload, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/auth";
import { mediaUrl } from "@/components/Attachments";
import { VcpConnect } from "@/components/VcpConnect";
import { useRecorder, blobName, clock } from "@/lib/recorder";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const VOICES = [["nova", "Nova — energetic"], ["shimmer", "Shimmer — bright"], ["coral", "Coral — warm"], ["alloy", "Alloy — neutral"], ["ash", "Ash — clear"],
  ["echo", "Echo — calm"], ["fable", "Fable — expressive"], ["onyx", "Onyx — deep"], ["sage", "Sage — measured"]];

const ENGINES = { "voxcpm2-vcp": "VoxCPM2 · Voice Creator Pro", "voxcpm2-hf": "VoxCPM2 · default voice", "voxcpm2-hf-clone": "VoxCPM2 · seller voice clone", openai: "OpenAI" };
const MAX_SECONDS = 30;

const BUSY_KM = "The Khmer voice is busy or down right now. Customers get the reply as text until it is back. Try again in a minute.";

const Preview = ({ text, label, testid, s }) => {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const run = async () => {
    setBusy(true);
    setErr("");
    try { setRes((await api.post("/voice/test", { text, voice: s.voice })).data); }
    catch (e) { const m = e?.response?.data?.detail ? errMsg(e) : /[\u1780-\u17FF]/.test(text) ? BUSY_KM : "Voice preview failed. Please try again."; setRes(null); setErr(m); toast.error(m); }
    finally { setBusy(false); }
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

const btn = "inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold disabled:opacity-50";

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
      toast.success(`Seller voice saved (${data.seconds} s)`);
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const stopAndUpload = async () => { const blob = await rec.stop(); if (blob) upload(blob, blobName(blob)); };
  useEffect(() => { if (rec.recording && rec.seconds >= MAX_SECONDS) stopAndUpload(); }, [rec.recording, rec.seconds]); // eslint-disable-line react-hooks/exhaustive-deps
  const toggleRec = async () => {
    if (rec.recording) return stopAndUpload();
    try { await rec.start(); } catch { toast.error("Please allow microphone access"); }
  };
  const remove = async () => {
    try { await api.delete("/settings/seller-voice"); setS((x) => ({ ...x, seller_voice_media_id: "", seller_voice_text: "" })); toast.success("Seller voice removed — the default voice is used"); }
    catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="space-y-3 border-t border-white/10 pt-4" data-testid="seller-voice">
      <div>
        <p className="font-medium text-sm">Seller’s own voice (voice clone)</p>
        <p className="text-xs text-slate-400 mt-1 leading-relaxed">Record or upload 5–30 seconds of the seller speaking Khmer naturally in a quiet room. VoxCPM2 copies the voice, rhythm and emotion. Without a sample, the default young woman’s voice is used.</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={toggleRec} disabled={busy} data-testid="seller-voice-record-btn"
          className={`${btn} ${rec.recording ? "bg-red-500 text-white" : "border border-white/10 hover:bg-white/5"}`}>
          {rec.recording ? <><Square className="h-3.5 w-3.5" /> Stop {clock(rec.seconds)} / {clock(MAX_SECONDS)}</> : <><Mic className="h-3.5 w-3.5" /> Record</>}
        </button>
        <button type="button" onClick={() => fileRef.current?.click()} disabled={busy || rec.recording} data-testid="seller-voice-upload-btn" className={`${btn} border border-white/10 hover:bg-white/5`}>
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />} {busy ? "Saving…" : "Upload audio"}
        </button>
        <input ref={fileRef} type="file" accept="audio/*" className="hidden" data-testid="seller-voice-input"
          onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) upload(f, f.name); }} />
        {s.seller_voice_media_id && <>
          <audio controls preload="metadata" src={`${mediaUrl(s.seller_voice_media_id)}?auth=${localStorage.getItem("rf_token")}`} className="h-9" data-testid="seller-voice-audio" />
          <button type="button" onClick={remove} data-testid="seller-voice-delete-btn" className={`${btn} border border-white/10 text-slate-400 hover:text-red-300`}><Trash2 className="h-3.5 w-3.5" /> Remove</button>
        </>}
      </div>
      {s.seller_voice_media_id && <>
        <label className="block"><span className="text-xs text-slate-400 mb-1.5 block">Exact words spoken in the sample (filled in automatically — fix any mistakes, then press Save at the top)</span>
          <Textarea rows={2} value={s.seller_voice_text} onChange={(e) => setS((x) => ({ ...x, seller_voice_text: e.target.value }))} data-testid="seller-voice-text" />
        </label>
        <Preview s={s} text="សួស្តីបង! អរគុណដែលបានទាក់ទងមកហាងយើងខ្ញុំ។ តើបងចង់កុម្ម៉ង់អ្វីដែរថ្ងៃនេះ?" label="Test seller voice" testid="seller-voice-preview-btn" />
      </>}
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
          Khmer replies are spoken by VoxCPM2: first by your own Voice Creator Pro (if connected below), otherwise by the free official Hugging Face demo, in the seller’s own voice if a sample is added below, or else a warm, friendly young woman’s voice.
          If no voice is ready within 60 seconds, customers get the reply as text instead.
        </p>
      </div>
      <Preview s={s} text="សួស្តីបង! អរគុណដែលបានទាក់ទងមកហាងយើងខ្ញុំ។ តើខ្ញុំអាចជួយអ្វីបានដែរ?" label="Test Khmer voice" testid="khmer-preview-btn" />
      <VcpConnect s={s} setS={setS} />
      <SellerVoice s={s} setS={setS} />
    </div>
  </Section>
);
