import { useState } from "react";
import { ImageOff, CheckCircle2, Clock, XCircle, ExternalLink, Check } from "lucide-react";
import { BACKEND_URL } from "@/lib/auth";

export const mediaUrl = (id) => `${BACKEND_URL}/api/media/${id}`;

export const AudioAtt = ({ a, testid }) => (
  <audio controls preload="metadata" src={a.url || mediaUrl(a.media_id)} className="h-9 w-56 max-w-full" data-testid={testid} />
);

export const ProductCard = ({ p, testid }) => (
  <div className="min-w-0 rounded-xl overflow-hidden border border-border bg-muted/50" data-testid={testid}>
    {p.media_id ? <img src={mediaUrl(p.media_id)} alt={p.name} className="aspect-square w-full object-cover" loading="lazy" />
      : <div className="aspect-square grid place-items-center text-muted-foreground/60"><ImageOff className="h-6 w-6" /></div>}
    <div className="px-3 py-2">
      <p className="text-xs font-semibold leading-snug line-clamp-2">{p.name}</p>
      {p.price && <p className="text-xs text-emerald-600 dark:text-emerald-400 font-semibold mt-0.5">{p.price}</p>}
    </div>
  </div>
);

const KHQR_STATE = {
  pending: [Clock, "text-amber-700 dark:text-amber-300", (a) => `Scan to pay · valid until ${new Date(a.expires_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`],
  paid: [CheckCircle2, "text-emerald-600 dark:text-emerald-400", () => "Paid — thank you!"],
  expired: [XCircle, "text-muted-foreground", () => "QR expired — ask for a new one"],
  cancelled: [XCircle, "text-muted-foreground/80", () => "Replaced by a newer QR"],
};

export const KhqrCard = ({ a, testid, onMarkPaid }) => {
  const [Icon, cls, label] = KHQR_STATE[a.status] || KHQR_STATE.pending;
  const [confirm, setConfirm] = useState(false);
  const markPaid = () => {
    if (a.status === "pending" || confirm) return onMarkPaid(a.order_id);
    setConfirm(true);
    setTimeout(() => setConfirm(false), 4000);
  };
  return (
    <div className="w-52 max-w-full rounded-2xl overflow-hidden border border-border bg-white" data-testid={testid}>
      <img src={mediaUrl(a.media_id)} alt={`KHQR ${a.amount_text}`} className={`w-full ${a.status === "pending" || a.status === "paid" ? "" : "opacity-40 grayscale"}`} />
      <div className="bg-muted/50 px-3 py-2.5 space-y-1.5">
        <p className="text-sm font-bold text-foreground flex justify-between gap-2"><span>{a.amount_text}</span><span className="font-mono text-[11px] text-muted-foreground/80 self-center">{a.number}</span></p>
        <p className={`text-[11px] flex items-center gap-1 ${cls}`} data-testid={`${testid}-status`}><Icon className="h-3.5 w-3.5 shrink-0" /> {label(a)}</p>
        {a.status === "pending" && a.deeplink && <a href={a.deeplink} target="_blank" rel="noreferrer" data-testid={`${testid}-deeplink`}
          className="flex items-center justify-center gap-1 rounded-lg bg-red-600 text-white py-1.5 text-xs font-semibold hover:bg-red-500"><ExternalLink className="h-3.5 w-3.5" /> Pay with Bakong</a>}
        {onMarkPaid && a.status !== "paid" && <button type="button" onClick={markPaid} data-testid={`${testid}-mark-paid`}
          className="w-full flex items-center justify-center gap-1 rounded-lg border border-emerald-500/40 text-emerald-700 dark:text-emerald-300 py-1.5 text-xs font-semibold hover:bg-emerald-500/10"><Check className="h-3.5 w-3.5" /> {confirm ? "Really received? Click again" : "Mark paid"}</button>}
      </div>
    </div>
  );
};

export const Attachments = ({ atts = [], prefix, onMarkPaid }) => {
  const audio = atts.filter((a) => a.type === "audio");
  const products = atts.filter((a) => a.type === "product");
  const khqr = atts.filter((a) => a.type === "khqr");
  if (!audio.length && !products.length && !khqr.length) return null;
  return (
    <div className="space-y-2">
      {audio.map((a, i) => <AudioAtt key={i} a={a} testid={`${prefix}-audio`} />)}
      {products.length > 0 && (
        <div className={`grid gap-2 max-w-full ${products.length === 1 ? "grid-cols-1 w-44" : "grid-cols-2 w-[22rem]"}`}>{products.map((p) => <ProductCard key={p.product_id} p={p} testid={`${prefix}-product`} />)}</div>
      )}
      {khqr.map((a) => <KhqrCard key={a.order_id} a={a} testid={`${prefix}-khqr`} onMarkPaid={onMarkPaid} />)}
    </div>
  );
};
