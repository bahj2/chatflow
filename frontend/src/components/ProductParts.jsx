import { Minus, Plus, Package, Boxes, AlertTriangle, PackageX } from "lucide-react";

export const LOW = 3;
export const stockState = (p) => (p.stock == null ? "untracked" : p.stock <= 0 ? "out" : p.stock <= LOW ? "low" : "in");

const PILL = {
  untracked: ["In stock", "text-emerald-700 dark:text-emerald-300 bg-emerald-500/10 border-emerald-500/30"],
  in: ["", "text-emerald-700 dark:text-emerald-300 bg-emerald-500/10 border-emerald-500/30"],
  low: ["", "text-amber-700 dark:text-amber-300 bg-amber-500/10 border-amber-500/30"],
  out: ["Sold out", "text-red-700 dark:text-red-300 bg-red-500/10 border-red-500/30"],
};

export const StockPill = ({ p }) => {
  const st = stockState(p);
  const [label, cls] = PILL[st];
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-semibold ${cls}`} data-testid={`product-stock-${p.id}`}>{label || `${p.stock} in stock`}</span>;
};

export const StockStepper = ({ p, onSet }) => (
  <div className="flex items-center rounded-full border border-border" data-testid={`product-stepper-${p.id}`}>
    <button onClick={() => onSet(p, Math.max(0, p.stock - 1))} disabled={p.stock <= 0} data-testid={`product-stock-minus-${p.id}`} className="h-7 w-7 grid place-items-center rounded-full hover:bg-muted disabled:opacity-40"><Minus className="h-3.5 w-3.5" /></button>
    <span className="min-w-[2ch] text-center font-mono text-xs">{p.stock}</span>
    <button onClick={() => onSet(p, p.stock + 1)} data-testid={`product-stock-plus-${p.id}`} className="h-7 w-7 grid place-items-center rounded-full hover:bg-muted"><Plus className="h-3.5 w-3.5" /></button>
  </div>
);

const CARDS = [
  ["all", "Total products", Package, "text-primary bg-primary/10"],
  ["in", "In stock", Boxes, "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10"],
  ["low", `Low stock (≤${LOW})`, AlertTriangle, "text-amber-600 dark:text-amber-400 bg-amber-500/10"],
  ["out", "Sold out", PackageX, "text-red-600 dark:text-red-400 bg-red-500/10"],
];

export const countBy = (items) => ({
  all: items.length,
  in: items.filter((p) => ["in", "untracked", "low"].includes(stockState(p))).length,
  low: items.filter((p) => stockState(p) === "low").length,
  out: items.filter((p) => stockState(p) === "out").length,
});

export const SummaryCards = ({ items, view, onView }) => {
  const n = countBy(items);
  return (
    <div className="mt-6 grid grid-cols-2 lg:grid-cols-4 gap-3" data-testid="products-summary">
      {CARDS.map(([k, label, Icon, tone]) => (
        <button key={k} onClick={() => onView(view === k ? "all" : k)} data-testid={`products-summary-${k}`}
          className={`text-left rounded-2xl border bg-card p-4 card-shadow transition-[border-color,transform] duration-200 hover:-translate-y-0.5 ${view === k && k !== "all" ? "border-primary/60 ring-1 ring-primary/20" : "border-border"}`}>
          <span className={`grid h-8 w-8 place-items-center rounded-lg ${tone}`}><Icon className="h-4 w-4" /></span>
          <p className="mt-3 font-display text-2xl font-bold" data-testid={`products-summary-${k}-value`}>{n[k]}</p>
          <p className="text-xs text-muted-foreground">{label}</p>
        </button>
      ))}
    </div>
  );
};

export const CategoryChips = ({ cats, value, onChange }) => cats.length > 0 && (
  <div className="flex flex-wrap gap-1.5" data-testid="products-categories">
    {["", ...cats].map((c) => (
      <button key={c || "all"} onClick={() => onChange(c)} data-testid={`products-category-${c || "all"}`}
        className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors duration-200 ${value === c ? "bg-foreground text-background" : "border border-border text-muted-foreground hover:text-foreground hover:bg-muted"}`}>
        {c || "All categories"}
      </button>
    ))}
  </div>
);
