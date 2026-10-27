import { useEffect, useState } from "react";
import { CreditCard, Check, Loader2, Plus, QrCode, CheckCircle2, Clock, Infinity as InfinityIcon, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg, BACKEND_URL } from "@/lib/auth";
import { useBilling, PLAN_FEATURES } from "@/lib/billing";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";

const day = (iso) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
const STATUS = {
  paid: "text-emerald-700 dark:text-emerald-300 bg-emerald-500/10 border-emerald-500/30",
  pending: "text-amber-700 dark:text-amber-300 bg-amber-500/10 border-amber-500/30",
  expired: "text-muted-foreground bg-muted border-border",
};

const Pill = ({ children, cls, testid }) => <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${cls}`} data-testid={testid}>{children}</span>;

const planStatus = (s) => {
  if (s.exempt) return ["Unlimited", STATUS.paid];
  if (s.paused) return [s.reason === "ended" ? "Ended" : "Paused", "text-red-600 dark:text-red-300 bg-red-500/10 border-red-500/30"];
  return [s.plan === "trial" ? "Trial" : "Active", STATUS.paid];
};

const Meter = ({ s }) => {
  const pct = Math.min(100, Math.round((s.used / Math.max(1, s.limit)) * 100));
  return (
    <div data-testid="billing-usage">
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-semibold"><span data-testid="billing-used">{s.used.toLocaleString()}</span> / {s.limit.toLocaleString()} AI replies</span>
        <span className="text-xs text-muted-foreground">resets {day(s.period_end)}</span>
      </div>
      <div className="mt-2 h-2.5 rounded-full bg-muted overflow-hidden"><div className={`h-full rounded-full ${pct >= 100 ? "bg-red-500" : "bg-brand"}`} style={{ width: `${pct}%` }} /></div>
      {(s.extra > 0 || s.extra_used > 0) && <p className="mt-2 text-xs text-muted-foreground" data-testid="billing-extra">+ {s.extra.toLocaleString()} extra replies left</p>}
    </div>
  );
};

const CurrentPlan = ({ s, topup, canTopup, onBuy, busy }) => {
  const [label, cls] = planStatus(s);
  const reason = s.reason === "ended" ? (s.plan === "trial" ? "Your free trial has ended." : "Your plan has ended.") : "All AI replies for this month are used.";
  return (
    <div className="rounded-2xl border border-border bg-card p-6 card-shadow space-y-5" data-testid="billing-current">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground">Current plan</p>
          <p className="font-display text-2xl font-bold mt-1 flex items-center gap-3"><span data-testid="billing-plan-name">{s.plan_name}</span><Pill cls={cls} testid="billing-plan-status">{label}</Pill></p>
          {!s.exempt && <p className="text-sm text-muted-foreground mt-1" data-testid="billing-days-left">{s.active ? `${s.days_left} day${s.days_left === 1 ? "" : "s"} left · ${s.plan === "trial" ? "ends" : "paid until"} ${day(s.paid_until)}` : `Ended ${day(s.paid_until)}`}</p>}
        </div>
        {!s.exempt && s.plan !== "trial" && (
          <button onClick={onBuy} disabled={!canTopup || busy} data-testid="billing-topup-btn" className="inline-flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-sm font-semibold hover:bg-muted disabled:opacity-50">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} {topup.replies.toLocaleString()} more replies · ${topup.price}
          </button>
        )}
      </div>
      {s.exempt ? <p className="text-sm text-muted-foreground flex items-center gap-2"><InfinityIcon className="h-4 w-4 text-primary" /> Your platform account has unlimited AI replies and is never billed.</p> : <Meter s={s} />}
      {s.paused && <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-300" data-testid="billing-paused-note">{reason} AI replies are paused, but customer messages still reach your inbox. Choose a plan below to turn them back on.</p>}
    </div>
  );
};

const PlanCard = ({ p, s, ready, onChoose, busy }) => {
  const current = s.plan === p.key && s.active;
  const popular = p.key === "pro";
  return (
    <div className={`relative flex flex-col rounded-2xl border bg-card p-6 card-shadow ${popular ? "border-primary/60" : "border-border"}`} data-testid={`plan-card-${p.key}`}>
      {popular && <span className="absolute -top-3 left-6 rounded-full bg-brand px-3 py-1 text-[11px] font-bold text-white flex items-center gap-1"><Sparkles className="h-3 w-3" />Most popular</span>}
      <p className="font-display text-lg font-semibold">{p.name}</p>
      <p className="mt-2"><span className="font-display text-4xl font-extrabold">${p.price}</span><span className="text-muted-foreground text-sm"> / month</span></p>
      <p className="mt-1 text-sm font-semibold text-primary">{p.replies.toLocaleString()} AI replies / month</p>
      <ul className="mt-5 space-y-2 flex-1">
        {PLAN_FEATURES[p.key].map((f) => <li key={f} className="flex gap-2 text-sm text-foreground/80"><Check className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400 mt-0.5" />{f}</li>)}
      </ul>
      {!s.exempt && (
        <button onClick={() => onChoose(p.key)} disabled={!ready || busy} data-testid={`plan-choose-${p.key}`}
          className={`mt-6 w-full rounded-full py-2.5 text-sm font-semibold disabled:opacity-50 ${popular ? "btn-brand" : "border border-border hover:bg-muted"}`}>
          {busy ? "Preparing QR…" : current ? "Renew for 30 days" : s.plan === "trial" || !s.active ? "Choose plan" : "Switch to this plan"}
        </button>
      )}
    </div>
  );
};

const useCountdown = (iso) => {
  const [left, setLeft] = useState(0);
  useEffect(() => {
    const tick = () => setLeft(Math.max(0, Math.floor((new Date(iso).getTime() - Date.now()) / 1000)));
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [iso]);
  return left;
};

const PayDialog = ({ inv, onClose, onPaid }) => {
  const [cur, setCur] = useState(inv);
  const left = useCountdown(inv.expires_at);
  useEffect(() => {
    if (cur.status !== "pending") return undefined;
    const t = setInterval(async () => {
      try {
        const { data } = await api.get(`/billing/invoices/${inv.id}`);
        setCur(data);
        if (data.status === "paid") onPaid();
      } catch { /* keep polling */ }
    }, 4000);
    return () => clearInterval(t);
  }, [cur.status, inv.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const expired = cur.status === "expired" || (cur.status === "pending" && left === 0);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm" data-testid="billing-pay-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><QrCode className="h-5 w-5 text-rose-600" /> Pay with Bakong KHQR</DialogTitle>
          <DialogDescription>{cur.item_name} · <b className="text-foreground">${cur.amount.toFixed(2)}</b> · invoice {cur.number}</DialogDescription>
        </DialogHeader>
        {cur.status === "paid" ? (
          <div className="py-6 text-center space-y-2" data-testid="billing-pay-success">
            <CheckCircle2 className="h-12 w-12 mx-auto text-emerald-500" />
            <p className="font-display text-lg font-semibold">Payment received</p>
            <p className="text-sm text-muted-foreground">Thank you! Your plan is updated.</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className={`rounded-2xl bg-white p-3 ${expired ? "opacity-30" : ""}`}><img src={`${BACKEND_URL}/api/billing/invoices/${cur.id}/qr.png`} alt="KHQR" className="w-full" data-testid="billing-pay-qr" /></div>
            <p className="text-sm text-center flex items-center justify-center gap-1.5" data-testid="billing-pay-countdown">
              <Clock className="h-4 w-4 text-muted-foreground" />{expired ? "This QR has expired. Close and choose the plan again." : `Valid for ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")} · scan with ABA, ACLEDA, Wing or any bank app`}
            </p>
            {cur.deeplink && !expired && <a href={cur.deeplink} className="block w-full rounded-full btn-brand py-2.5 text-center text-sm font-semibold" data-testid="billing-pay-deeplink">Open in my bank app</a>}
            <p className="text-xs text-muted-foreground text-center">{cur.mode === "relay" ? "This window updates by itself after you pay." : "After you pay, Replyflow AI confirms it and your plan turns on (usually within a few hours)."}</p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

const History = ({ invoices }) => invoices.length > 0 && (
  <div className="rounded-2xl border border-border bg-card overflow-x-auto card-shadow">
    <table className="w-full text-sm min-w-[520px]" data-testid="billing-history">
      <thead className="text-xs text-muted-foreground text-left"><tr><th className="px-5 py-3">Invoice</th><th className="px-5 py-3">Item</th><th className="px-5 py-3">Amount</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Date</th></tr></thead>
      <tbody>
        {invoices.map((i) => (
          <tr key={i.id} className="border-t border-border/60" data-testid={`billing-invoice-${i.id}`}>
            <td className="px-5 py-3 font-mono text-xs">{i.number}</td><td className="px-5 py-3">{i.item_name}</td><td className="px-5 py-3">${i.amount.toFixed(2)}</td>
            <td className="px-5 py-3"><Pill cls={STATUS[i.status] || STATUS.expired}>{i.status}</Pill></td><td className="px-5 py-3 text-muted-foreground">{day(i.created_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

export default function BillingPanel() {
  const { billing, refresh } = useBilling();
  const [busy, setBusy] = useState("");
  const [inv, setInv] = useState(null);
  useEffect(() => { refresh(); }, [refresh]);
  if (!billing) return <div className="p-8 text-muted-foreground">Loading…</div>;
  const { sub: s, plans, topup, payments_ready: ready, invoices } = billing;
  const buy = async (item) => {
    setBusy(item);
    try { setInv((await api.post("/billing/checkout", { item })).data); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-8">
        <div>
          <h1 className="font-display text-3xl font-bold flex items-center gap-3"><CreditCard className="h-7 w-7 text-primary" /> Billing</h1>
          <p className="text-sm text-muted-foreground mt-1">Your plan, AI replies used this month, and payments by Bakong KHQR.</p>
        </div>
        <CurrentPlan s={s} topup={topup} canTopup={ready && s.active && s.plan !== "trial"} onBuy={() => buy("topup")} busy={busy === "topup"} />
        {!s.exempt && !ready && <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-800 dark:text-amber-200" data-testid="billing-not-ready">Online payment isn&apos;t set up yet. Please contact Replyflow AI to choose a plan.</p>}
        <div className="grid md:grid-cols-3 gap-5 pt-2">
          {plans.map((p) => <PlanCard key={p.key} p={p} s={s} ready={ready} onChoose={buy} busy={busy === p.key} />)}
        </div>
        {!s.exempt && <p className="text-xs text-muted-foreground">Plans last 30 days. Renewing adds 30 days; switching plans starts a new 30-day period right away. Extra replies stay until your plan ends.</p>}
        <History invoices={invoices} />
      </div>
      {inv && <PayDialog inv={inv} onClose={() => { setInv(null); refresh(); }} onPaid={() => { refresh(); toast.success("Payment received — thank you!"); }} />}
    </div>
  );
}
