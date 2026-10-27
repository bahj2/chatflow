import { useCallback, useEffect, useState } from "react";
import { Receipt } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/auth";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const PLANS = [["starter", "Starter"], ["pro", "Pro"], ["business", "Business"]];
const RECENT_MS = 48 * 3600 * 1000;
const when = (iso) => new Date(iso).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export const PlanCell = ({ b }) => {
  const s = b.billing;
  if (!s) return <span className="text-xs text-muted-foreground/80">—</span>;
  if (s.exempt) return <span className="text-xs font-semibold text-primary" data-testid={`admin-plan-${b.id}`}>Platform</span>;
  const state = s.paused ? (s.reason === "ended" ? "Ended" : "Replies used up") : `${s.days_left} d left`;
  return (
    <div className="leading-tight" data-testid={`admin-plan-${b.id}`}>
      <p className="font-semibold text-sm">{s.plan_name}</p>
      <p className={`text-[11px] whitespace-nowrap ${s.paused ? "text-red-600 dark:text-red-300" : "text-emerald-700 dark:text-emerald-300"}`}>{state} · {s.used.toLocaleString()}/{s.limit.toLocaleString()}</p>
    </div>
  );
};

export const SetPlanDialog = ({ b, onClose, onDone }) => {
  const cur = b.billing?.plan;
  const [plan, setPlan] = useState(cur && cur !== "trial" ? cur : "pro");
  const [days, setDays] = useState(30);
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try { await api.post(`/admin/businesses/${b.id}/plan`, { plan, days: Number(days) }); toast.success(`${b.name}: plan turned on`); onDone(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm" data-testid="admin-set-plan-dialog">
        <DialogHeader>
          <DialogTitle>Turn on a plan</DialogTitle>
          <DialogDescription>{b.name} — e.g. after a cash or bank transfer. If the same plan is still running, the days are added to it.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Select value={plan} onValueChange={setPlan}>
            <SelectTrigger data-testid="admin-set-plan-select"><SelectValue /></SelectTrigger>
            <SelectContent>{PLANS.map(([k, l]) => <SelectItem key={k} value={k} data-testid={`admin-set-plan-${k}`}>{l}</SelectItem>)}</SelectContent>
          </Select>
          <label className="block"><span className="text-xs text-muted-foreground mb-1.5 block">Days</span>
            <Input type="number" min={1} max={366} value={days} onChange={(e) => setDays(e.target.value)} data-testid="admin-set-plan-days" /></label>
          <button onClick={save} disabled={busy || !(days >= 1 && days <= 366)} data-testid="admin-set-plan-save" className="w-full rounded-full btn-brand py-2.5 text-sm font-semibold disabled:opacity-60">{busy ? "Saving…" : "Turn on plan"}</button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

const InvoiceRow = ({ i, armed, onConfirm }) => (
  <li className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3" data-testid={`admin-invoice-${i.id}`}>
    <div className="flex-1 min-w-[180px]">
      <p className="text-sm font-semibold">{i.business_name || "Unknown shop"} · ${i.amount.toFixed(2)}</p>
      <p className="text-xs text-muted-foreground">{i.item_name} · <span className="font-mono">{i.number}</span> · {when(i.created_at)}{i.status === "expired" ? " · QR expired" : ""}</p>
    </div>
    <button onClick={() => onConfirm(i)} data-testid={`admin-invoice-confirm-${i.id}`}
      className={`rounded-full px-4 py-1.5 text-xs font-semibold transition-colors duration-200 ${armed ? "bg-emerald-600 text-white" : "border border-border hover:bg-muted"}`}>
      {armed ? "Click again to confirm" : "Money received"}
    </button>
  </li>
);

export const PendingInvoices = ({ onChange }) => {
  const [items, setItems] = useState([]);
  const [armed, setArmed] = useState("");
  const load = useCallback(() => api.get("/admin/invoices", { params: { status: "all" } }).then((r) =>
    setItems(r.data.filter((i) => ["pending", "expired"].includes(i.status) && Date.now() - new Date(i.created_at).getTime() < RECENT_MS))).catch(() => {}), []);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);
  const confirm = async (i) => {
    if (armed !== i.id) { setArmed(i.id); setTimeout(() => setArmed(""), 3000); return; }
    try { await api.post(`/admin/invoices/${i.id}/confirm`); toast.success(`${i.business_name}: payment confirmed, plan is on`); load(); onChange(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="rounded-xl border border-border bg-card" data-testid="admin-pending-invoices">
      <div className="px-4 py-3 border-b border-border/60">
        <p className="font-semibold text-sm flex items-center gap-2"><Receipt className="h-4 w-4 text-primary" /> Plan payments to check</p>
        <p className="text-xs text-muted-foreground mt-0.5">KHQR invoices from the last 2 days. With a KHQR.dev token in your AI Settings they turn on by themselves; otherwise confirm here once the money is in your Bakong account.</p>
      </div>
      {items.length === 0 ? <p className="px-4 py-4 text-sm text-muted-foreground/80" data-testid="admin-invoices-empty">No payments waiting.</p>
        : <ul className="divide-y divide-border/60">{items.map((i) => <InvoiceRow key={i.id} i={i} armed={armed === i.id} onConfirm={confirm} />)}</ul>}
    </div>
  );
};
