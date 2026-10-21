import { Sparkles, RefreshCw, Target, ArrowRight, Loader2 } from "lucide-react";

const STAGE = {
  "Hot lead": "text-rose-300 bg-rose-500/10 border-rose-500/30",
  "New lead": "text-emerald-300 bg-emerald-500/10 border-emerald-500/30",
  Complaint: "text-red-300 bg-red-500/10 border-red-500/30",
  Support: "text-sky-300 bg-sky-500/10 border-sky-500/30",
  Resolved: "text-slate-300 bg-slate-500/10 border-slate-500/30",
};

export const StageTag = ({ stage }) => (
  <span className={`inline-block shrink-0 whitespace-nowrap rounded-full border px-2 py-0.5 text-[10px] font-semibold ${STAGE[stage] || "text-amber-300 bg-amber-500/10 border-amber-500/30"}`} data-testid="summary-stage">{stage}</span>
);

export const SummaryStrip = ({ summary, loading }) => (
  <div className="xl:hidden flex items-center gap-2 px-5 py-2 border-b border-white/5 bg-amber-400/[0.04] text-xs min-w-0" data-testid="summary-strip">
    {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-300 shrink-0" /> : <Sparkles className="h-3.5 w-3.5 text-amber-300 shrink-0" />}
    {summary ? <><StageTag stage={summary.stage} /><span className="truncate text-slate-300">{summary.intent} — {summary.summary}</span></>
      : <span className="text-slate-500">{loading ? "Reading the conversation…" : "No summary yet"}</span>}
  </div>
);

export const SummaryPanel = ({ summary, loading, onRefresh }) => (
  <aside className="hidden xl:flex flex-col w-[300px] shrink-0 border-l border-white/5 bg-[#0D121C] p-5 gap-5 overflow-y-auto" data-testid="summary-panel">
    <div className="flex items-center justify-between">
      <p className="font-mono text-[11px] uppercase tracking-widest text-amber-300 flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5" /> AI summary</p>
      <button onClick={onRefresh} disabled={loading} data-testid="summary-refresh-btn" className="text-slate-500 hover:text-white disabled:opacity-50" title="Refresh">
        <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
      </button>
    </div>
    {!summary && <p className="text-sm text-slate-500">{loading ? "Reading the conversation…" : "The summary appears once the customer writes."}</p>}
    {summary && (
      <>
        <div className="space-y-2">
          <StageTag stage={summary.stage} />
          <p className="font-display text-lg font-semibold leading-snug flex gap-2" data-testid="summary-intent"><Target className="h-4 w-4 mt-1.5 text-amber-300 shrink-0" />{summary.intent}</p>
          <p className="text-sm text-slate-300 leading-relaxed" data-testid="summary-text">{summary.summary}</p>
        </div>
        {summary.details?.length > 0 && (
          <div>
            <p className="text-[11px] font-mono uppercase tracking-widest text-slate-500 mb-2">Key details</p>
            <ul className="space-y-1.5" data-testid="summary-details">
              {summary.details.map((d, i) => <li key={i} className="text-sm text-slate-200 border-l-2 border-amber-400/40 pl-2.5">{d}</li>)}
            </ul>
          </div>
        )}
        {summary.next_step && (
          <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/[0.06] p-3.5">
            <p className="text-[11px] font-mono uppercase tracking-widest text-emerald-400 mb-1 flex items-center gap-1"><ArrowRight className="h-3 w-3" /> Next step</p>
            <p className="text-sm text-slate-200" data-testid="summary-next-step">{summary.next_step}</p>
          </div>
        )}
      </>
    )}
  </aside>
);
