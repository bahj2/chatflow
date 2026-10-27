import { useEffect, useState } from "react";
import { Send, Facebook, CheckCircle2, Circle, Loader2, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg, BACKEND_URL, useAuth } from "@/lib/auth";
import { OwnerOnly } from "@/components/SettingsPanel";
import { Input } from "@/components/ui/input";
import { Section, Field } from "@/components/SettingsPanel";
import { FacebookConnect, MetaSetupCard, CopyBox } from "@/components/FacebookConnect";


const Status = ({ ok, label }) => (
  <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${ok ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground/80"}`} data-testid={`status-${label.toLowerCase().replace(/\s/g, "-")}`}>
    {ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Circle className="h-3.5 w-3.5" />}{label}
  </span>
);

const Head = ({ Icon, color, name }) => (
  <span className="flex items-center gap-2"><Icon className="h-5 w-5" style={{ color }} />{name}</span>
);

const SaveBtn = ({ which, label, busy, onSave }) => (
  <button onClick={() => onSave(which)} disabled={!!busy} data-testid={`save-${which}-btn`}
    className="inline-flex items-center gap-2 rounded-full btn-brand px-5 py-2 text-sm font-semibold disabled:opacity-60">
    {busy === which && <Loader2 className="h-4 w-4 animate-spin" />}{label}
  </button>
);

export default function ChannelsPanel() {
  const { user } = useAuth();
  const owner = user?.role !== "member";
  const [s, setS] = useState(null);
  const [st, setSt] = useState(null);
  const [busy, setBusy] = useState("");
  const loadStatus = () => api.get("/channels/status").then((r) => setSt(r.data));
  useEffect(() => { api.get("/settings").then((r) => setS((cur) => cur || r.data)); loadStatus(); }, []);
  const refresh = () => { loadStatus(); api.get("/settings").then((r) => setS(r.data)); };
  if (!s) return <div className="p-8 text-muted-foreground/80">Loading…</div>;

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

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <h1 className="font-display text-3xl font-bold">Channels</h1>
        <p className="text-sm text-muted-foreground mt-1">Connect your channels once. Everything else is automatic.</p>

        <Section title={<Head Icon={Send} color="#229ED9" name="Telegram" />} desc="Open @BotFather in Telegram → /newbot → copy the token here.">
          <div className="flex gap-4"><Status ok={st?.telegram.configured} label="Token saved" /><Status ok={st?.telegram.connected} label="Webhook connected" /></div>
          {st?.telegram.bot && <p className="text-sm" data-testid="telegram-bot-name">Bot: <a className="text-sky-600 dark:text-sky-400" href={`https://t.me/${st.telegram.bot}`} target="_blank" rel="noreferrer">@{st.telegram.bot}</a></p>}
          {owner ? <>
            <Field label="Bot token"><Input type="password" value={s.telegram_token} onChange={set("telegram_token")} placeholder="123456789:AA..." data-testid="telegram-token-input" /></Field>
            <SaveBtn which="telegram" label="Save & connect" busy={busy} onSave={save} />
          </> : <OwnerOnly testid="owner-only-telegram" />}
        </Section>

        <Section title={<Head Icon={Facebook} color="#0084FF" name="Messenger" />} desc="Connect your Facebook Page so Messenger chats land in your Inbox and the AI answers them.">
          <FacebookConnect owner={owner} manualConfigured={!!st?.messenger.manual} allowManual={user.role === "superadmin"} onChanged={refresh} manual={<>
            <Status ok={st?.messenger.manual} label="Configured" />
            <p className="text-xs text-muted-foreground">In Meta for Developers: create an app → add Messenger → generate a Page access token → set the webhook below with your verify token, subscribe to &apos;messages&apos;.</p>
            <Field label="Callback URL (paste into Meta webhook settings)"><CopyBox value={`${BACKEND_URL}/api/webhooks/messenger/${user.business_id}`} testid="messenger-callback-url" /></Field>
            <div className="grid sm:grid-cols-3 gap-4">
              <Field label="Page access token"><Input type="password" value={s.fb_page_token} onChange={set("fb_page_token")} data-testid="fb-page-token-input" /></Field>
              <Field label="App secret (App settings → Basic)"><Input type="password" value={s.fb_app_secret} onChange={set("fb_app_secret")} data-testid="fb-app-secret-input" /></Field>
              <Field label="Verify token (any secret word)"><Input value={s.fb_verify_token} onChange={set("fb_verify_token")} data-testid="fb-verify-token-input" /></Field>
            </div>
            <p className="text-xs text-muted-foreground/80 flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" /> Every incoming message is checked with your App secret — fake messages are rejected.</p>
            <SaveBtn which="messenger" label="Save" busy={busy} onSave={save} />
          </>} />
        </Section>

        {user.role === "superadmin" && <MetaSetupCard Section={Section} />}
      </div>
    </div>
  );
}
