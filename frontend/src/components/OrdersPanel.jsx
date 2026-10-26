import { useCallback, useEffect, useState } from "react";
import { Receipt, Loader2, Check, X } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/auth";
import { mediaUrl } from "@/components/Attachments";
import { ChannelBadge } from "@/components/ChannelBadge";

const FILTERS = [["", "All"], ["pending", "Waiting"], ["paid", "Paid"], ["expired", "Expired"], ["cancelled", "Cancelled"]];
export const STATUS = {
  pending: ["Waiting for payment", "bg-amber-400/10 text-amber-700 dark:text-amber-300 border-amber-400/30"],
  paid: ["Paid", "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30"],
  expired: ["Expired", "bg-slate-500/10 text-muted-foreground border-border"],
  cancelled: ["Cancelled", "bg-red-500/10 text-red-600 dark:text-red-300 border-red-500/30"],
};
const money = (o) => (o.currency === "KHR" ? `${Math.round(o.total).toLocaleString()}៛` : `$${o.total.toFixed(2)}`);
const when = (iso) => (iso ? new Date(iso).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "");

export const StatusPill = ({ status, testid }) => {
  const [label, cls] = STATUS[status] || [status, "border-border"];
  return <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${cls}`} data-testid={testid}>{label}</span>;
};

const OrderRow = ({ o, onAction }) => {
  const [confirm, setConfirm] = useState(false);
  const markPaid = () => {
    if (o.status === "pending" || confirm) return onAction(o, "mark-paid");
    setConfirm(true);
    setTimeout(() => setConfirm(false), 4000);
  };
  return (
  <li className="flex flex-col sm:flex-row gap-4 rounded-xl border border-border bg-card p-4" data-testid={`order-${o.number}`}>
    <img src={mediaUrl(o.qr_media_id)} alt="KHQR" className="w-20 h-28 object-cover object-top rounded-lg shrink-0" />
    <div className="flex-1 min-w-0 space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm font-semibold">{o.number}</span>
        <StatusPill status={o.status} testid={`order-status-${o.number}`} />
        <ChannelBadge channel={o.channel} compact />
        <span className="text-[11px] text-muted-foreground/80">{o.mode === "relay" ? "auto-check" : "manual"}</span>
      </div>
      <p className="text-sm text-foreground/80 truncate">{o.customer} · {o.items.map((i) => `${i.qty}× ${i.name}`).join(", ")}</p>
      <p className="text-[11px] text-muted-foreground/80">{when(o.created_at)}{o.paid_at ? ` · paid ${when(o.paid_at)}${o.paid_by && o.paid_by !== "auto" ? " (marked by seller)" : " (automatic)"}` : ""}</p>
    </div>
    <div className="flex sm:flex-col items-center sm:items-end justify-between gap-2 shrink-0">
      <span className="text-lg font-bold text-emerald-700 dark:text-emerald-300" data-testid={`order-total-${o.number}`}>{money(o)}</span>
      {o.status !== "paid" && (
        <div className="flex gap-2">
          <button onClick={markPaid} data-testid={`order-mark-paid-${o.number}`} title={o.status === "pending" ? "" : "This QR expired or was replaced — only confirm if you really received this payment"}
            className="inline-flex items-center gap-1 rounded-lg btn-brand px-3 py-1.5 text-xs font-semibold"><Check className="h-3.5 w-3.5" /> {confirm ? "Really received? Click again" : "Mark paid"}</button>
          {o.status !== "cancelled" && <button onClick={() => onAction(o, "cancel")} data-testid={`order-cancel-${o.number}`}
            className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-red-600 dark:hover:text-red-300"><X className="h-3.5 w-3.5" /> Cancel</button>}
        </div>
      )}
    </div>
  </li>
  );
};

export default function OrdersPanel() {
  const [orders, setOrders] = useState(null);
  const [filter, setFilter] = useState("");
  const load = useCallback(() => api.get("/orders", { params: { status: filter || undefined } }).then((r) => setOrders(r.data)), [filter]);
  useEffect(() => { load(); const t = setInterval(load, 8000); return () => clearInterval(t); }, [load]);
  const onAction = async (o, action) => {
    try { await api.post(`/orders/${o.id}/${action}`); toast.success(action === "cancel" ? "Order cancelled" : "Marked as paid — the customer was told"); load(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const paid = (orders || []).filter((o) => o.status === "paid");
  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto px-6 lg:px-10 py-8 space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl font-bold flex items-center gap-2"><Receipt className="h-6 w-6 text-emerald-600 dark:text-emerald-400" /> Orders</h1>
            <p className="text-sm text-muted-foreground mt-1">Orders the AI created, each with a Bakong KHQR for the exact total.</p>
          </div>
          {paid.length > 0 && <p className="text-xs text-muted-foreground" data-testid="orders-paid-count">{paid.length} paid in this list</p>}
        </div>
        <div className="flex flex-wrap gap-1" data-testid="orders-filters">
          {FILTERS.map(([v, l]) => (
            <button key={v || "all"} onClick={() => setFilter(v)} data-testid={`orders-filter-${v || "all"}`}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${filter === v ? "bg-foreground text-background" : "text-muted-foreground hover:bg-muted/60"}`}>{l}</button>
          ))}
        </div>
        {!orders ? <Loader2 className="h-5 w-5 animate-spin text-muted-foreground/80" />
          : orders.length === 0 ? <p className="text-sm text-muted-foreground/80" data-testid="orders-empty">No orders yet. When a customer confirms a purchase in chat, it shows up here.</p>
          : <ul className="space-y-3" data-testid="orders-list">{orders.map((o) => <OrderRow key={o.id} o={o} onAction={onAction} />)}</ul>}
      </div>
    </div>
  );
}
