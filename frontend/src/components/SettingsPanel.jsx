import { useEffect, useState } from "react";
import { Plus, Trash2, Save, Sparkles, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/auth";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Attachments } from "@/components/Attachments";
import { VoiceSection } from "@/components/VoiceSettings";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const Section = ({ title, desc, children }) => (
  <section className="grid lg:grid-cols-[260px_1fr] gap-6 py-8 border-b border-white/5">
    <div><h2 className="font-display text-lg font-semibold">{title}</h2><p className="text-sm text-slate-400 mt-1">{desc}</p></div>
    <div className="space-y-4 min-w-0">{children}</div>
  </section>
);

export const Field = ({ label, children }) => (
  <label className="block"><span className="text-xs font-medium text-slate-400 mb-1.5 block">{label}</span>{children}</label>
);

const Pick = ({ value, onChange, items, testid }) => (
  <Select value={value} onValueChange={onChange}>
    <SelectTrigger data-testid={testid}><SelectValue /></SelectTrigger>
    <SelectContent>{items.map(([v, l]) => <SelectItem key={v} value={v} data-testid={`${testid}-${v}`}>{l}</SelectItem>)}</SelectContent>
  </Select>
);

const Tester = () => {
  const [q, setQ] = useState("");
  const [a, setA] = useState(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    if (!q.trim()) return;
    setBusy(true);
    try { setA((await api.post("/ai/test", { text: q })).data); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.04] p-4 space-y-3">
      <div className="flex gap-2">
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask like a customer would…" data-testid="ai-test-input" onKeyDown={(e) => e.key === "Enter" && run()} />
        <button onClick={run} disabled={busy} data-testid="ai-test-btn" className="shrink-0 inline-flex items-center gap-1.5 rounded-lg bg-emerald-500 text-slate-950 px-4 text-sm font-semibold hover:bg-emerald-400 disabled:opacity-60">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} Test
        </button>
      </div>
      {a && <p className="text-sm text-slate-200 whitespace-pre-wrap" data-testid="ai-test-reply">{a.reply}</p>}
      {a?.products?.length > 0 && <Attachments atts={a.products} prefix="ai-test" />}
    </div>
  );
};

export default function SettingsPanel() {
  const [s, setS] = useState(null);
  const [saving, setSaving] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  useEffect(() => { api.get("/settings").then((r) => setS((cur) => cur || r.data)); }, []);
  if (!s) return <div className="p-8 text-slate-500">Loading…</div>;

  const set = (k) => (v) => setS({ ...s, [k]: v?.target ? v.target.value : v });
  const setFaq = (i, k, v) => setS({ ...s, faqs: s.faqs.map((f, j) => (j === i ? { ...f, [k]: v } : f)) });
  const setQr = (i, k, v) => setS({ ...s, quick_replies: s.quick_replies.map((f, j) => (j === i ? { ...f, [k]: v } : f)) });
  const addEmail = () => {
    const em = newEmail.trim().toLowerCase();
    if (!/^\S+@\S+\.\S+$/.test(em)) return toast.error("Enter a valid email");
    if (!s.allowed_emails.includes(em)) setS({ ...s, allowed_emails: [...s.allowed_emails, em] });
    setNewEmail("");
  };
  const save = async () => {
    setSaving(true);
    try { await api.put("/settings", s); toast.success("Settings saved"); } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between gap-4">
          <div><h1 className="font-display text-3xl font-bold">AI Settings</h1><p className="text-sm text-slate-400 mt-1">Teach the AI about your business.</p></div>
          <button onClick={save} disabled={saving} data-testid="save-settings-btn"
            className="inline-flex items-center gap-2 rounded-full bg-emerald-500 text-slate-950 px-5 py-2.5 text-sm font-semibold hover:bg-emerald-400 disabled:opacity-60">
            <Save className="h-4 w-4" /> {saving ? "Saving…" : "Save"}
          </button>
        </div>

        <Section title="Business" desc="What you do, what you sell, prices, hours, delivery, policies.">
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Business name"><Input value={s.business_name} onChange={set("business_name")} data-testid="business-name-input" /></Field>
            <Field label="Business type">
              <Pick value={s.business_type} onChange={set("business_type")} testid="business-type-select"
                items={[["generic", "General business"], ["online shop", "Online shop"], ["services", "Services / bookings"]]} />
            </Field>
          </div>
          <Field label="Business information">
            <Textarea rows={7} value={s.business_info} onChange={set("business_info")} data-testid="business-info-input"
              placeholder="e.g. We sell handmade leather bags. Prices from $40. Free delivery over $100. Open Mon–Sat 9:00–18:00. Payment: card or cash on delivery." />
          </Field>
          <Field label="Greeting on website chat"><Input value={s.greeting} onChange={set("greeting")} data-testid="greeting-input" /></Field>
        </Section>

        <Section title="FAQs" desc="Common questions and the exact answers you want the AI to use.">
          {s.faqs.map((f, i) => (
            <div key={i} className="rounded-xl border border-white/10 bg-[#0F1522] p-4 space-y-2" data-testid={`faq-item-${i}`}>
              <div className="flex gap-2">
                <Input value={f.q} onChange={(e) => setFaq(i, "q", e.target.value)} placeholder="Question" data-testid={`faq-q-${i}`} />
                <button onClick={() => setS({ ...s, faqs: s.faqs.filter((_, j) => j !== i) })} data-testid={`faq-delete-${i}`} className="text-slate-500 hover:text-red-400 px-2"><Trash2 className="h-4 w-4" /></button>
              </div>
              <Textarea rows={2} value={f.a} onChange={(e) => setFaq(i, "a", e.target.value)} placeholder="Answer" data-testid={`faq-a-${i}`} />
            </div>
          ))}
          <button onClick={() => setS({ ...s, faqs: [...s.faqs, { q: "", a: "" }] })} data-testid="add-faq-btn"
            className="inline-flex items-center gap-1.5 text-sm text-emerald-400 hover:text-emerald-300"><Plus className="h-4 w-4" /> Add FAQ</button>
        </Section>

        <Section title="Team access" desc="Teammates’ Google emails. When they click “Continue with Google” they join this business’s inbox (instead of creating their own).">
          <div className="flex gap-2">
            <Input value={newEmail} onChange={(e) => setNewEmail(e.target.value)} placeholder="name@gmail.com" type="email" data-testid="allowed-email-input"
              onKeyDown={(e) => e.key === "Enter" && addEmail()} />
            <button onClick={addEmail} data-testid="add-allowed-email-btn" className="shrink-0 inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-4 text-sm hover:bg-white/5"><Plus className="h-4 w-4" /> Add</button>
          </div>
          <div className="flex flex-wrap gap-2" data-testid="allowed-emails-list">
            {s.allowed_emails.length === 0 && <p className="text-xs text-slate-500">No Google accounts yet — add your Gmail, then click Save.</p>}
            {s.allowed_emails.map((em) => (
              <span key={em} className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-[#0F1522] pl-3 pr-1.5 py-1 text-sm" data-testid={`allowed-email-${em}`}>
                {em}
                <button onClick={() => setS({ ...s, allowed_emails: s.allowed_emails.filter((x) => x !== em) })} data-testid={`remove-allowed-email-${em}`} className="text-slate-500 hover:text-red-400"><Trash2 className="h-3.5 w-3.5" /></button>
              </span>
            ))}
          </div>
        </Section>

        <Section title="Quick replies" desc="Saved answers (prices, address, hours…) that send with one tap from the inbox.">
          {s.quick_replies.map((r, i) => (
            <div key={i} className="rounded-xl border border-white/10 bg-[#0F1522] p-4 space-y-2" data-testid={`quick-item-${i}`}>
              <div className="flex gap-2">
                <Input value={r.label} onChange={(e) => setQr(i, "label", e.target.value)} placeholder="Button label, e.g. Prices" data-testid={`quick-label-${i}`} />
                <button onClick={() => setS({ ...s, quick_replies: s.quick_replies.filter((_, j) => j !== i) })} data-testid={`quick-delete-${i}`} className="text-slate-500 hover:text-red-400 px-2"><Trash2 className="h-4 w-4" /></button>
              </div>
              <Textarea rows={2} value={r.text} onChange={(e) => setQr(i, "text", e.target.value)} placeholder="Message that will be sent" data-testid={`quick-text-${i}`} />
            </div>
          ))}
          <button onClick={() => setS({ ...s, quick_replies: [...s.quick_replies, { label: "", text: "" }] })} data-testid="add-quick-btn"
            className="inline-flex items-center gap-1.5 text-sm text-emerald-400 hover:text-emerald-300"><Plus className="h-4 w-4" /> Add quick reply</button>
        </Section>

        <VoiceSection s={s} setS={setS} Section={Section} Field={Field} />

        <Section title="AI behaviour" desc="Model, tone and language for every reply.">
          <div className="grid sm:grid-cols-3 gap-4">
            <Field label="AI model">
              <Pick value={s.model} onChange={set("model")} testid="model-select" items={[["claude", "Claude Sonnet 4.5"], ["gemini", "Gemini 3 Flash"]]} />
            </Field>
            <Field label="Tone">
              <Pick value={s.tone} onChange={set("tone")} testid="tone-select" items={[["friendly", "Friendly"], ["professional", "Professional"], ["direct", "Short & direct"], ["witty", "Witty"]]} />
            </Field>
            <Field label="Reply language">
              <Pick value={s.language} onChange={set("language")} testid="language-select"
                items={[["auto", "Same as customer"], ["English", "English"], ["Russian", "Russian"], ["Ukrainian", "Ukrainian"], ["Spanish", "Spanish"], ["Vietnamese", "Vietnamese"], ["Thai", "Thai"]]} />
            </Field>
          </div>
          <div className="flex items-center justify-between rounded-xl border border-white/10 bg-[#0F1522] p-4">
            <div><p className="font-medium text-sm">Auto-reply on all channels</p><p className="text-xs text-slate-400">Turn off to only use suggested replies.</p></div>
            <Switch checked={s.auto_reply} onCheckedChange={set("auto_reply")} data-testid="auto-reply-switch" />
          </div>
          <Field label="Try it (save first to test new info)"><Tester /></Field>
        </Section>
      </div>
    </div>
  );
}
