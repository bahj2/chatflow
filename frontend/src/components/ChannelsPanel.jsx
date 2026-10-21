import { useEffect, useState } from "react";
import { Copy, Send, Facebook, Globe, CheckCircle2, Circle, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg, BACKEND_URL } from "@/lib/auth";
import { Input } from "@/components/ui/input";
import { Section, Field } from "@/components/SettingsPanel";

const CopyBox = ({ value, testid }) => (
  <div className="flex gap-2">
    <code className="flex-1 truncate rounded-lg bg-slate-900 border border-white/10 px-3 py-2 text-xs font-mono text-slate-300" data-testid={testid}>{value}</code>
    <button onClick={() => { navigator.clipboard.writeText(value); toast.success("Copied"); }} data-testid={`${testid}-copy`}
      className="shrink-0 rounded-lg border border-white/10 px-3 hover:bg-white/5"><Copy className="h-4 w-4" /></button>
  </div>
);

const Status = ({ ok, label }) => (
  <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${ok ? "text-emerald-400" : "text-slate-500"}`} data-testid={`status-${label.toLowerCase().replace(/\s/g, "-")}`}>
    {ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Circle className="h-3.5 w-3.5" />}{label}
  </span>
);

const Head = ({ Icon, color, name }) => (
  <span className="flex items-center gap-2"><Icon className="h-5 w-5" style={{ color }} />{name}</span>
);

export default function ChannelsPanel() {
  const [s, setS] = useState(null);
  const [st, setSt] = useState(null);
  const [busy, setBusy] = useState("");
  const loadStatus = () => api.get("/channels/status").then((r) => setSt(r.data));
  useEffect(() => { api.get("/settings").then((r) => setS((cur) => cur || r.data)); loadStatus(); }, []);
  if (!s) return <div className="p-8 text-slate-500">Loading…</div>;

  const set = (k) => (e) => setS({ ...s, [k]: e.target.value });
  const save = async (which) => {
    setBusy(which);
    try {
      await api.put("/settings", s);
      if (which === "telegram") {
        const { data } = await api.post("/channels/telegram/connect", { base_url: BACKEND_URL });
        toast.success(`Connected @${data.bot}`);
      } else toast.success("Saved");
      loadStatus();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  const Btn = ({ which, label }) => (
    <button onClick={() => save(which)} disabled={!!busy} data-testid={`save-${which}-btn`}
      className="inline-flex items-center gap-2 rounded-full bg-emerald-500 text-slate-950 px-5 py-2 text-sm font-semibold hover:bg-emerald-400 disabled:opacity-60">
      {busy === which && <Loader2 className="h-4 w-4 animate-spin" />}{label}
    </button>
  );

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <h1 className="font-display text-3xl font-bold">Channels</h1>
        <p className="text-sm text-slate-400 mt-1">Paste your tokens when you have them. Everything else is automatic.</p>

        <Section title={<Head Icon={Send} color="#229ED9" name="Telegram" />} desc="Open @BotFather in Telegram → /newbot → copy the token here.">
          <div className="flex gap-4"><Status ok={st?.telegram.configured} label="Token saved" /><Status ok={st?.telegram.connected} label="Webhook connected" /></div>
          {st?.telegram.bot && <p className="text-sm" data-testid="telegram-bot-name">Bot: <a className="text-sky-400" href={`https://t.me/${st.telegram.bot}`} target="_blank" rel="noreferrer">@{st.telegram.bot}</a></p>}
          <Field label="Bot token"><Input type="password" value={s.telegram_token} onChange={set("telegram_token")} placeholder="123456789:AA..." data-testid="telegram-token-input" /></Field>
          <Btn which="telegram" label="Save & connect" />
        </Section>

        <Section title={<Head Icon={Facebook} color="#0084FF" name="Messenger" />} desc="In Meta for Developers: create an app → add Messenger → generate a Page access token → set the webhook below with your verify token, subscribe to 'messages'.">
          <Status ok={st?.messenger.configured} label="Configured" />
          <Field label="Callback URL (paste into Meta webhook settings)"><CopyBox value={`${BACKEND_URL}/api/webhooks/messenger`} testid="messenger-callback-url" /></Field>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Page access token"><Input type="password" value={s.fb_page_token} onChange={set("fb_page_token")} data-testid="fb-page-token-input" /></Field>
            <Field label="Verify token (any secret word you choose)"><Input value={s.fb_verify_token} onChange={set("fb_verify_token")} data-testid="fb-verify-token-input" /></Field>
          </div>
          <Btn which="messenger" label="Save" />
        </Section>

        <Section title={<Head Icon={Globe} color="#10B981" name="Website chat" />} desc="Already live on your landing page — the chat bubble in the corner.">
          <Status ok label="Active" />
          <Field label="Your website"><CopyBox value={window.location.origin} testid="website-url" /></Field>
        </Section>
      </div>
    </div>
  );
}
