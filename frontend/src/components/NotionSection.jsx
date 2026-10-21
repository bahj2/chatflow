import { useCallback, useEffect, useRef, useState } from "react";
import { BookOpen, CheckCircle2, ExternalLink, Loader2, RefreshCw, Unlink, AlertTriangle, XCircle, FileText, Table2 } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/auth";
import { Input } from "@/components/ui/input";

const NOTION_INTEGRATIONS = "https://www.notion.so/profile/integrations";
const BUSY = ["queued", "syncing"];

const ago = (iso) => {
  if (!iso) return "never";
  const m = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  return h < 24 ? `${h} h ago` : `${Math.round(h / 24)} d ago`;
};

const Num = ({ n }) => <span className="shrink-0 h-7 w-7 rounded-full grid place-items-center text-xs font-bold bg-white/5 border border-white/15">{n}</span>;

const Step = ({ n, title, children, testid }) => (
  <li className="flex gap-3 rounded-xl border border-white/10 bg-[#0B0F17] p-4 min-w-0" data-testid={testid}>
    <Num n={n} />
    <div className="flex-1 min-w-0 space-y-2 pt-0.5"><p className="text-sm font-semibold">{title}</p>{children}</div>
  </li>
);

const ShareHelp = () => (
  <p className="text-xs text-slate-400 leading-relaxed">
    In Notion, open the page with your shop info → click <b className="text-slate-200">•••</b> (top right) → <b className="text-slate-200">Connections</b> → add <b className="text-slate-200">ReplyFlow</b>.
    Sharing one parent page also shares every page inside it.
  </p>
);

const SecretForm = ({ onDone, label = "Connect" }) => {
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { onDone((await api.post("/notion/connect", { token: token.trim() })).data); setToken(""); toast.success("Notion connected — reading your pages…"); }
    catch (err) { toast.error(errMsg(err)); } finally { setBusy(false); }
  };
  return (
    <form onSubmit={submit} className="flex flex-col sm:flex-row gap-2" data-testid="notion-connect-form">
      <Input type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} placeholder="ntn_…" data-testid="notion-token-input" />
      <button type="submit" disabled={busy || !token.trim()} data-testid="notion-connect-btn"
        className="shrink-0 inline-flex items-center justify-center gap-1.5 rounded-lg bg-emerald-500 text-slate-950 px-4 py-2 text-sm font-semibold hover:bg-emerald-400 disabled:opacity-50">
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <BookOpen className="h-4 w-4" />} {label}
      </button>
    </form>
  );
};

const ConnectSteps = ({ onDone }) => (
  <ol className="space-y-2.5" data-testid="notion-setup-steps">
    <Step n={1} title="Create a ReplyFlow connection in Notion" testid="notion-step-1">
      <p className="text-xs text-slate-400 leading-relaxed">Click <b className="text-slate-200">New integration</b>, name it <b className="text-slate-200">ReplyFlow</b>, choose your workspace and save. Then copy the <b className="text-slate-200">Internal Integration Secret</b> (it starts with ntn_).</p>
      <a href={NOTION_INTEGRATIONS} target="_blank" rel="noreferrer" data-testid="notion-open-integrations-link"
        className="inline-flex items-center gap-1.5 rounded-full border border-white/15 px-4 py-2 text-xs font-semibold hover:bg-white/5">
        <ExternalLink className="h-3.5 w-3.5" /> Open Notion integrations
      </a>
    </Step>
    <Step n={2} title="Share your pages with ReplyFlow" testid="notion-step-2"><ShareHelp /></Step>
    <Step n={3} title="Paste the secret here" testid="notion-step-3"><SecretForm onDone={onDone} /></Step>
  </ol>
);

const StatusPill = ({ n }) => {
  if (BUSY.includes(n.status)) return <span className="inline-flex items-center gap-1.5 text-xs text-emerald-300" data-testid="notion-status"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Reading your Notion pages…</span>;
  if (n.status === "ok") return <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400" data-testid="notion-status"><CheckCircle2 className="h-3.5 w-3.5" /> Synced {ago(n.last_sync_at)} · {n.page_count} page{n.page_count === 1 ? "" : "s"}</span>;
  if (n.status === "invalid") return <span className="inline-flex items-center gap-1.5 text-xs text-red-400" data-testid="notion-status"><XCircle className="h-3.5 w-3.5" /> Secret no longer works</span>;
  return <span className="inline-flex items-center gap-1.5 text-xs text-amber-300" data-testid="notion-status"><AlertTriangle className="h-3.5 w-3.5" /> Last sync failed</span>;
};

const PageList = ({ pages }) => (
  <ul className="max-h-64 overflow-y-auto divide-y divide-white/5 rounded-xl border border-white/10 bg-[#0B0F17]" data-testid="notion-pages-list">
    {pages.map((p, i) => (
      <li key={p.url || i} className="flex items-center gap-3 px-4 py-2.5 text-sm min-w-0" data-testid={`notion-page-${i}`}>
        {p.kind === "row" ? <Table2 className="h-4 w-4 shrink-0 text-sky-400" /> : <FileText className="h-4 w-4 shrink-0 text-slate-400" />}
        <span className="flex-1 min-w-0 truncate">{p.title}</span>
        <span className="text-[11px] font-mono text-slate-500 shrink-0">{p.chars} chars</span>
        {p.url && <a href={p.url} target="_blank" rel="noreferrer" className="text-slate-500 hover:text-slate-200 shrink-0" data-testid={`notion-page-link-${i}`}><ExternalLink className="h-3.5 w-3.5" /></a>}
      </li>
    ))}
  </ul>
);

const Connected = ({ n, setN }) => {
  const [confirm, setConfirm] = useState(false);
  const sync = async () => { try { setN((await api.post("/notion/sync")).data); } catch (e) { toast.error(errMsg(e)); } };
  const disconnect = async () => {
    if (!confirm) { setConfirm(true); setTimeout(() => setConfirm(false), 3000); return; }
    try { setN((await api.delete("/notion")).data); toast.success("Notion disconnected"); } catch (e) { toast.error(errMsg(e)); }
  };
  const busy = BUSY.includes(n.status);
  return (
    <div className="space-y-4" data-testid="notion-connected">
      <div className="rounded-xl border border-white/10 bg-[#0F1522] p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium text-sm" data-testid="notion-workspace">Connected to {n.workspace || "your Notion workspace"}</p>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1"><StatusPill n={n} /><span className="text-[11px] font-mono text-slate-500">secret ••••{n.hint}</span></div>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={sync} disabled={busy} data-testid="notion-sync-btn"
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold hover:bg-white/5 disabled:opacity-50">
            <RefreshCw className={`h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`} /> Sync now
          </button>
          <button type="button" onClick={disconnect} data-testid="notion-disconnect-btn"
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold transition-colors duration-200 ${confirm ? "bg-red-500 text-white" : "border border-white/10 text-slate-400 hover:text-red-300"}`}>
            <Unlink className="h-3.5 w-3.5" /> {confirm ? "Click again to disconnect" : "Disconnect"}
          </button>
        </div>
      </div>
      {n.last_error && !busy && <p className="text-xs text-red-300" data-testid="notion-error">{n.last_error}</p>}
      {n.status === "invalid" && <div className="space-y-2" data-testid="notion-reconnect"><p className="text-xs text-slate-400">Paste a new secret from Notion to reconnect:</p><SecretForm onDone={setN} label="Reconnect" /></div>}
      {n.status === "ok" && n.page_count === 0 && (
        <div className="rounded-xl border border-amber-400/30 bg-amber-400/[0.05] p-4 space-y-1.5" data-testid="notion-no-pages">
          <p className="text-sm font-medium text-amber-200">No pages shared yet</p><ShareHelp /><p className="text-xs text-slate-400">Then click Sync now.</p>
        </div>
      )}
      {n.pages?.length > 0 && <PageList pages={n.pages} />}
      {n.truncated && <p className="text-xs text-amber-300" data-testid="notion-truncated">Your pages are long — the AI reads the first 30,000 characters (most recently edited pages first). Share only the pages customers need.</p>}
      <p className="text-[11px] text-slate-500">Updates automatically every hour. After editing Notion, click Sync now to update right away.</p>
    </div>
  );
};

export const NotionSection = ({ Section }) => {
  const [n, setN] = useState(null);
  const timer = useRef(null);
  const load = useCallback(async () => { try { setN((await api.get("/notion")).data); } catch { /* keep last state */ } }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    clearTimeout(timer.current);
    if (n && BUSY.includes(n.status)) timer.current = setTimeout(load, 2500);
    return () => clearTimeout(timer.current);
  }, [n, load]);
  return (
    <Section title="Notion knowledge" desc="Let the AI read your Notion pages — shop info, FAQs, prices and policies — and answer customers from them.">
      <div data-testid="notion-section">
        {!n ? <Loader2 className="h-4 w-4 animate-spin text-slate-500" /> : n.connected ? <Connected n={n} setN={setN} /> : <ConnectSteps onDone={setN} />}
      </div>
    </Section>
  );
};
