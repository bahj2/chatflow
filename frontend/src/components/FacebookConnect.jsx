import { useEffect, useRef, useState } from "react";
import { Copy, Facebook, CheckCircle2, Circle, Loader2, AlertTriangle, ChevronDown, ExternalLink, Unplug, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg, BACKEND_URL } from "@/lib/auth";
import { OwnerOnly } from "@/components/SettingsPanel";

const FB_BLUE = "#1877F2";

export const CopyBox = ({ value, testid }) => (
  <div className="flex gap-2 min-w-0">
    <code className="flex-1 min-w-0 truncate rounded-lg bg-muted/50 border border-border px-3 py-2 text-xs font-mono text-foreground/80" data-testid={testid}>{value}</code>
    <button onClick={() => { navigator.clipboard.writeText(value); toast.success("Copied"); }} data-testid={`${testid}-copy`}
      className="shrink-0 rounded-lg border border-border px-3 hover:bg-muted/60"><Copy className="h-4 w-4" /></button>
  </div>
);

const FbButton = ({ onClick, busy, disabled, label, testid }) => (
  <button onClick={onClick} disabled={busy || disabled} data-testid={testid} style={{ backgroundColor: FB_BLUE }}
    className="inline-flex items-center justify-center gap-2.5 rounded-full px-6 py-3 text-sm font-semibold text-white shadow-sm hover:brightness-110 disabled:opacity-60 transition">
    {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Facebook className="h-5 w-5" fill="white" strokeWidth={0} />} {label}
  </button>
);

/** Shop side: one click to log in with Facebook, pick the Page, done. Manual token setup stays available as "advanced". */
export function FacebookConnect({ owner, manual, manualConfigured, onChanged }) {
  const [meta, setMeta] = useState(null);
  const [pages, setPages] = useState(null);
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [showManual, setShowManual] = useState(false);
  const once = useRef(false);

  const load = () => api.get("/meta/status").then((r) => { setMeta(r.data); return r.data; }).catch(() => { setMeta({ available: false, connected: false }); return null; });

  const connectPage = async (id) => {
    setBusy("page"); setErr("");
    try {
      const { data } = await api.post(`/meta/facebook/pages/${id}/connect`);
      toast.success(`Messenger connected to ${data.page_name || "your Page"}`);
      setPages(null);
      await load();
      onChanged?.();
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(""); }
  };

  useEffect(() => {
    if (once.current) return;
    once.current = true;
    const q = new URLSearchParams(window.location.search);
    const e = q.get("fb_error");
    if (q.get("fb") || e) window.history.replaceState(null, "", window.location.pathname);
    if (e) setErr(e);
    // Back from Facebook (even if the ?fb=pick marker got lost on the way): finish connecting the Page
    load().then((m) => {
      if (!m || m.connected || !(m.pending || q.get("fb") === "pick")) return;
      api.get("/meta/facebook/pages").then((r) => {
        const free = r.data.filter((p) => !p.taken);
        if (r.data.length === 1 && free.length === 1) connectPage(free[0].id); // only one Page: no need to ask
        else { setPages(r.data); setPick(free[0]?.id || ""); }
      }).catch((x) => setErr(errMsg(x)));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const start = async () => {
    setBusy("start"); setErr("");
    try {
      const { data } = await api.post("/meta/facebook/start", { base_url: BACKEND_URL, return_url: window.location.origin });
      window.location.href = data.url;
    } catch (e) { setErr(errMsg(e)); setBusy(""); }
  };
  const disconnect = async () => {
    if (!window.confirm(`Disconnect ${meta.page_name || "this Page"}? Messenger chats will stop reaching your Inbox.`)) return;
    setBusy("off");
    try { await api.delete("/meta/facebook"); toast.success("Facebook Page disconnected"); await load(); onChanged?.(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };

  if (!meta) return <div className="text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin inline mr-2" />Checking Facebook…</div>;
  const manualOpen = showManual || manualConfigured || !meta.available;

  return (
    <div className="space-y-4" data-testid="fb-connect">
      {err && (
        <div className="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-300" data-testid="fb-error">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" /><span>{err}</span>
        </div>
      )}

      {meta.connected ? (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 flex flex-col sm:flex-row sm:items-center gap-3" data-testid="fb-connected">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <span className="grid place-items-center h-10 w-10 rounded-full shrink-0" style={{ backgroundColor: FB_BLUE }}><Facebook className="h-5 w-5 text-white" fill="white" strokeWidth={0} /></span>
            <div className="min-w-0">
              <p className="text-sm font-semibold truncate" data-testid="fb-page-name">{meta.page_name || "Your Facebook Page"}</p>
              <p className="text-xs text-emerald-700 dark:text-emerald-300 flex items-center gap-1"><CheckCircle2 className="h-3.5 w-3.5" /> Connected — Messenger chats arrive in your Inbox</p>
            </div>
          </div>
          {owner && (
            <div className="flex gap-2">
              <button onClick={start} disabled={!!busy} data-testid="fb-change-page-btn" className="inline-flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-xs font-semibold hover:bg-muted/60 disabled:opacity-60">
                {busy === "start" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />} Change page
              </button>
              <button onClick={disconnect} disabled={!!busy} data-testid="fb-disconnect-btn" className="inline-flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-xs font-semibold text-muted-foreground hover:text-red-600 dark:hover:text-red-400 disabled:opacity-60">
                {busy === "off" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Unplug className="h-3.5 w-3.5" />} Disconnect
              </button>
            </div>
          )}
        </div>
      ) : !owner ? <OwnerOnly testid="owner-only-messenger" /> : pages ? (
        <div className="rounded-xl border border-border bg-muted/40 p-4 space-y-3" data-testid="fb-page-picker">
          <p className="text-sm font-semibold">Which Page should Replyflow AI answer for?</p>
          <div className="space-y-2">
            {pages.map((p) => (
              <label key={p.id} className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 text-sm ${p.taken ? "opacity-50 cursor-not-allowed border-border" : pick === p.id ? "border-primary bg-primary/5 cursor-pointer" : "border-border cursor-pointer hover:bg-muted/60"}`} data-testid={`fb-page-option-${p.id}`}>
                <input type="radio" name="fb-page" value={p.id} checked={pick === p.id} disabled={p.taken} onChange={() => setPick(p.id)} className="accent-[#1877F2]" />
                <span className="flex-1 truncate">{p.name}</span>
                {p.taken && <span className="text-xs text-muted-foreground">used by another shop</span>}
              </label>
            ))}
          </div>
          <div className="flex gap-2">
            <FbButton onClick={() => connectPage(pick)} busy={busy === "page"} disabled={!pick} label="Connect this Page" testid="fb-connect-page-btn" />
            <button onClick={() => setPages(null)} className="rounded-full px-4 text-sm text-muted-foreground hover:text-foreground" data-testid="fb-pick-cancel">Cancel</button>
          </div>
        </div>
      ) : meta.available ? (
        <div className="space-y-2">
          <FbButton onClick={start} busy={busy === "start" || busy === "page"} label={busy === "page" ? "Connecting your Page…" : "Connect with Facebook"} testid="fb-connect-btn" />
          <p className="text-xs text-muted-foreground">Log in to Facebook, tick your Page, press Continue — that’s it. You need to be an admin of the Page.</p>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground" data-testid="fb-not-available">One-click “Connect with Facebook” isn’t switched on yet. You can connect manually below.</p>
      )}

      {owner && !meta.connected && manual && (
        <div className="border-t border-border pt-4">
          {meta.available && !manualConfigured && (
            <button onClick={() => setShowManual((v) => !v)} data-testid="fb-manual-toggle" className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground">
              <ChevronDown className={`h-3.5 w-3.5 transition ${manualOpen ? "rotate-180" : ""}`} /> Advanced: connect manually with your own Meta app
            </button>
          )}
          {manualOpen && <div className="space-y-4 mt-3" data-testid="fb-manual">{manual}</div>}
        </div>
      )}
    </div>
  );
}

const Check = ({ ok, label, optional }) => (
  <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${ok ? "text-emerald-600 dark:text-emerald-400" : optional ? "text-muted-foreground" : "text-amber-700 dark:text-amber-300"}`}>
    {ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Circle className="h-3.5 w-3.5" />}{label}{optional && !ok ? " (optional)" : ""}
  </span>
);

/** Platform admin only: the one-time Meta app setup that switches on the button for every shop. */
export function MetaSetupCard({ Section }) {
  const [d, setD] = useState(null);
  const [open, setOpen] = useState(false);
  const [hooking, setHooking] = useState(false);
  useEffect(() => { api.get("/admin/meta-setup", { params: { base_url: BACKEND_URL } }).then((r) => { setD(r.data); setOpen(!r.data.ready); }).catch(() => {}); }, []);
  if (!d) return null;
  const hookOk = d.webhook?.active && d.webhook?.messages && d.webhook?.url === d.webhook_url;
  const autoHook = async () => {
    setHooking(true);
    try { const { data } = await api.post("/admin/meta-setup/webhook", { base_url: BACKEND_URL }); setD({ ...d, webhook: data.webhook }); toast.success("Message webhook is set up — Facebook confirmed it"); }
    catch (e) { toast.error(errMsg(e)); } finally { setHooking(false); }
  };
  const host = new URL(BACKEND_URL).host;
  return (
    <Section title={<span className="flex items-center gap-2"><Facebook className="h-5 w-5" style={{ color: FB_BLUE }} /> Platform Facebook app (one-time setup)</span>}
      desc="Only you see this. Set it up once and every shop gets the one-click “Connect with Facebook” button.">
      <div className="space-y-4" data-testid="meta-setup">
        <div className="flex flex-wrap gap-4" data-testid="meta-setup-status">
          <Check ok={d.app_id_set} label="App ID" />
          <Check ok={d.app_secret_set} label="App secret" />
          <Check ok={d.config_id_set} label="Login configuration ID" optional />
          <Check ok={d.ready} label={d.ready ? `Button is on · ${d.pages_connected} page${d.pages_connected === 1 ? "" : "s"} connected` : "Button is off"} />
          {d.ready && <Check ok={hookOk} label={hookOk ? "Message webhook on" : "Message webhook not set"} />}
        </div>
        {d.ready && !hookOk && (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3" data-testid="meta-webhook-missing">
            <p className="text-sm flex-1 min-w-[12rem]">Facebook doesn’t send Page messages to this address yet{d.webhook?.url ? " (it points to another address)" : ""}. One click fixes it — no need to paste anything in Meta.</p>
            <button onClick={autoHook} disabled={hooking} data-testid="meta-webhook-auto-btn" style={{ backgroundColor: FB_BLUE }}
              className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold text-white disabled:opacity-60">
              {hooking && <Loader2 className="h-3.5 w-3.5 animate-spin" />} Set up message webhook
            </button>
          </div>
        )}
        <button onClick={() => setOpen((v) => !v)} data-testid="meta-setup-toggle" className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary">
          <ChevronDown className={`h-3.5 w-3.5 transition ${open ? "rotate-180" : ""}`} /> {open ? "Hide" : "Show"} the steps
        </button>
        {open && (
          <ol className="space-y-4 text-sm list-decimal pl-5 marker:font-semibold marker:text-muted-foreground" data-testid="meta-setup-steps">
            <li className="space-y-1">
              <p>Open <a href="https://developers.facebook.com/apps/" target="_blank" rel="noreferrer" className="text-primary inline-flex items-center gap-1">Meta for Developers <ExternalLink className="h-3 w-3" /></a> → <b>Create app</b>. Choose the use case <b>“Engage with customers on Messenger from Meta”</b> (or <b>Other → Business</b>) and link your Business portfolio.</p>
            </li>
            <li className="space-y-2">
              <p><b>App settings → Basic</b>: add App domain <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{host}</code> and a Privacy Policy URL. Copy the <b>App ID</b> and <b>App secret</b> and give them to the builder in chat — they go into a secure box, never into this page.</p>
            </li>
            <li className="space-y-2">
              <p><b>Facebook Login for Business → Settings</b>: turn on <b>Client OAuth login</b> and <b>Web OAuth login</b>, and paste this into <b>Valid OAuth Redirect URIs</b>:</p>
              <CopyBox value={d.redirect_uri} testid="meta-redirect-uri" />
              <p className="text-xs text-muted-foreground">Optional: <b>Configurations → Create</b> → “User access token” with the permissions below, then send the <b>Configuration ID</b> too.</p>
            </li>
            <li className="space-y-2">
              <p><b>Message webhook:</b> press <b>Set up message webhook</b> above (easiest), or in Meta open <b>Messenger → Settings → Webhooks</b>, paste the Callback URL and Verify token, press <b>Verify and save</b>, then subscribe to <b>messages</b>.</p>
              <CopyBox value={d.webhook_url} testid="meta-webhook-url" />
              <CopyBox value={d.verify_token} testid="meta-verify-token" />
            </li>
            <li className="space-y-1">
              <p>Permissions the button asks for:</p>
              <div className="flex flex-wrap gap-2">{d.permissions.map((p) => <code key={p} className="text-xs bg-muted px-2 py-1 rounded">{p}</code>)}</div>
            </li>
            <li className="space-y-1">
              <p><b>Test now:</b> under <b>App roles</b>, add your own Facebook account (and any shop owner who will test) as <b>Tester</b>. Until Meta approves the app, only these people can connect a Page and chat with it.</p>
            </li>
            <li className="space-y-1">
              <p><b>Open it to every shop:</b> complete <b>Business verification</b>, then in <b>App Review</b> request <b>Advanced access</b> for the three permissions. Attach a short screen recording: Channels → Connect with Facebook → pick a Page → message the Page → the AI replies. When approved, switch the app to <b>Live</b>.</p>
            </li>
          </ol>
        )}
        {!d.ready && <p className="text-xs text-muted-foreground">If you publish the app, open this card on the live site and use the addresses shown there instead of the ones above.</p>}
      </div>
    </Section>
  );
}
