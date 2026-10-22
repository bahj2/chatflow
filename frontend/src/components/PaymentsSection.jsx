import { useState } from "react";
import { QrCode, Loader2, CheckCircle2, Zap, Hand, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/auth";
import { Input } from "@/components/ui/input";
import { mediaUrl } from "@/components/Attachments";

const KHQR_DEV = "https://dash.khqr.dev";

const ModeBadge = ({ s }) => {
  const auto = (s.khqr_token || "").startsWith("rbk");
  const on = auto || /^[A-Za-z0-9._-]{2,40}@[A-Za-z0-9._-]{2,20}$/.test(s.bakong_account_id || "");
  if (!on) return <span className="text-xs text-slate-500" data-testid="payments-mode">Off — add your Bakong account ID to turn on KHQR payments</span>;
  return auto
    ? <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400" data-testid="payments-mode"><Zap className="h-3.5 w-3.5" /> Automatic — payments are confirmed by themselves (KHQR.dev)</span>
    : <span className="inline-flex items-center gap-1.5 text-xs text-amber-300" data-testid="payments-mode"><Hand className="h-3.5 w-3.5" /> Manual — tap “Mark paid” in Inbox or Orders after checking your bank app</span>;
};

const Preview = () => {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const run = async () => {
    setBusy(true);
    try { setRes((await api.post("/payments/preview")).data); } catch (e) { setRes(null); toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="flex flex-wrap items-start gap-4">
      <button type="button" onClick={run} disabled={busy} data-testid="payments-preview-btn"
        className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold hover:bg-white/5 disabled:opacity-60">
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <QrCode className="h-3.5 w-3.5" />} Preview a $1.00 KHQR (save first)
      </button>
      {res && (
        <div className="space-y-2" data-testid="payments-preview">
          <img src={mediaUrl(res.media_id)} alt="KHQR preview" className="w-40 rounded-xl" data-testid="payments-preview-img" />
          <p className="text-[11px] text-slate-500 max-w-[16rem]">Scan it with your bank app to check the name and account — no need to pay. Mode: {res.mode === "relay" ? "automatic" : "manual"}.</p>
        </div>
      )}
    </div>
  );
};

export const PaymentsSection = ({ s, setS, Section, Field }) => {
  const set = (k) => (e) => setS((x) => ({ ...x, [k]: e.target.value }));
  return (
    <Section title="Bakong KHQR payments" desc="When a customer confirms an order, the AI sends a KHQR with the exact total. Customers pay with any Cambodian bank app.">
      <div data-testid="payments-section" className="space-y-4">
        <ModeBadge s={s} />
        <div className="grid sm:grid-cols-3 gap-4">
          <Field label="Bakong account ID"><Input value={s.bakong_account_id || ""} onChange={set("bakong_account_id")} placeholder="name@aclb" data-testid="bakong-account-input" /></Field>
          <Field label="Name shown in the bank app"><Input value={s.bakong_merchant_name || ""} onChange={set("bakong_merchant_name")} maxLength={25} placeholder={s.business_name} data-testid="bakong-merchant-input" /></Field>
          <Field label="City"><Input value={s.bakong_city || ""} onChange={set("bakong_city")} maxLength={15} placeholder="Phnom Penh" data-testid="bakong-city-input" /></Field>
        </div>
        <div className="rounded-xl border border-white/10 bg-[#0F1522] p-4 space-y-3" data-testid="payments-auto-card">
          <div>
            <p className="font-medium text-sm flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Optional: confirm payments automatically</p>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Bakong’s own payment check only works from servers inside Cambodia. Create a free store at KHQR.dev with the same Bakong account, then paste its token (starts with rbk) here.
              ReplyFlow then sees each payment within seconds, marks the order Paid and thanks the customer.
            </p>
          </div>
          <div className="flex flex-col sm:flex-row gap-2">
            <Input type="password" autoComplete="off" value={s.khqr_token || ""} onChange={set("khqr_token")} placeholder="rbk_…" data-testid="khqr-token-input" />
            <a href={KHQR_DEV} target="_blank" rel="noreferrer" data-testid="khqr-dev-link"
              className="shrink-0 inline-flex items-center justify-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold hover:bg-white/5">
              <ExternalLink className="h-3.5 w-3.5" /> Get a token
            </a>
          </div>
        </div>
        <p className="text-[11px] text-slate-500">Write product prices like <b className="text-slate-300">10$</b> or <b className="text-slate-300">40000៛</b> so the AI can total orders. Each QR is valid for 10 minutes.</p>
        <Preview />
      </div>
    </Section>
  );
};
