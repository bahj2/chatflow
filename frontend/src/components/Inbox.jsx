import { useEffect, useMemo, useRef, useState } from "react";
import { Search, Sparkles, ArrowUp, Bot, User, Headphones, ArrowLeft, Loader2, Zap } from "lucide-react";
import { SummaryPanel, SummaryStrip } from "@/components/CustomerSummary";
import { Attachments, AudioAtt } from "@/components/Attachments";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/auth";
import { ChannelBadge } from "@/components/ChannelBadge";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

const FILTERS = ["all", "telegram", "messenger"];
const time = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "");
const when = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toDateString() === new Date().toDateString() ? time(iso) : d.toLocaleDateString([], { day: "numeric", month: "short" });
};

const ConvList = ({ convs, active, onPick, filter, setFilter, q, setQ, total, hasMore, onMore, loadingMore, listRef }) => (
  <div className="flex flex-col h-full border-r border-border/60 bg-surface">
    <div className="p-4 space-y-3 border-b border-border/60">
      <h1 className="font-display text-xl font-bold flex items-baseline gap-2">Inbox <span className="text-xs font-mono text-muted-foreground/80" data-testid="inbox-total">{total.toLocaleString()} chats</span></h1>
      <div className="relative">
        <Search className="h-4 w-4 absolute left-3 top-2.5 text-muted-foreground/80" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" data-testid="inbox-search-input"
          className="w-full bg-muted/50 border border-border rounded-lg pl-9 pr-3 py-2 text-sm outline-none focus:border-emerald-500/60" />
      </div>
      <div className="flex gap-1">
        {FILTERS.map((f) => (
          <button key={f} onClick={() => setFilter(f)} data-testid={`filter-${f}`}
            className={`px-2.5 py-1 rounded-md text-xs font-medium capitalize transition-colors ${filter === f ? "bg-foreground text-background" : "text-muted-foreground hover:bg-muted/60"}`}>{f}</button>
        ))}
      </div>
    </div>
    <div ref={listRef} className="flex-1 overflow-y-auto" data-testid="conversation-list"
      onScroll={(e) => { const el = e.currentTarget; if (hasMore && !loadingMore && el.scrollTop + el.clientHeight > el.scrollHeight - 300) onMore(); }}>
      {convs.length === 0 && <p className="p-6 text-sm text-muted-foreground/80" data-testid="inbox-empty">No conversations yet. Connect Telegram or Messenger in Channels.</p>}
      {convs.map((c) => (
        <button key={c.id} onClick={() => onPick(c)} data-testid={`conversation-item-${c.id}`}
          className={`w-full text-left px-4 py-3.5 border-b border-border/60 transition-colors ${active?.id === c.id ? "bg-primary/[0.07] border-l-2 border-l-primary" : "hover:bg-muted/40"}`}>
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold text-sm truncate">{c.name}</span>
            <span className="text-[11px] text-muted-foreground/80 shrink-0">{when(c.updated_at)}</span>
          </div>
          <div className="flex items-center gap-2 mt-1.5">
            <ChannelBadge channel={c.channel} compact />
            <span className="text-xs text-muted-foreground truncate flex-1">{c.last_message}</span>
            {c.summary?.intent && <span className="hidden sm:inline shrink-0 max-w-[110px] truncate text-[10px] font-semibold text-amber-700 dark:text-amber-300" data-testid={`conversation-intent-${c.id}`}>{c.summary.intent}</span>}
            {c.unread > 0 && <span className="h-5 min-w-5 px-1.5 rounded-full bg-brand text-foreground text-[11px] font-bold grid place-items-center">{c.unread}</span>}
          </div>
        </button>
      ))}
      {hasMore && (
        <button onClick={onMore} disabled={loadingMore} data-testid="load-more-btn" className="w-full py-4 text-xs text-muted-foreground hover:text-foreground flex items-center justify-center gap-2">
          {loadingMore && <Loader2 className="h-3.5 w-3.5 animate-spin" />} Load older chats
        </button>
      )}
    </div>
  </div>
);

const ROLE = {
  user: { Icon: User, label: "Customer", cls: "bg-muted border-border" },
  ai: { Icon: Bot, label: "AI auto-reply", cls: "bg-emerald-500/[0.08] border-emerald-500/30" },
  agent: { Icon: Headphones, label: "You", cls: "bg-indigo-500/[0.1] border-indigo-500/30" },
};

const Bubble = ({ m, onMarkPaid }) => {
  const r = ROLE[m.role];
  const mine = m.role !== "user";
  return (
    <div className={`flex ${mine ? "justify-end" : ""}`} data-testid={`message-${m.role}`}>
      <div className="max-w-[75%]">
        <p className={`text-[10px] font-mono uppercase tracking-wider text-muted-foreground/80 mb-1 flex items-center gap-1 ${mine ? "justify-end" : ""}`}>
          <r.Icon className="h-3 w-3" />{r.label} · {time(m.created_at)}
        </p>
        <div className={`border rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap space-y-1.5 ${r.cls}`}>
          {(m.attachments || []).filter((a) => a.type === "audio").map((a, i) => <AudioAtt key={i} a={a} testid={`message-${m.role}-audio`} />)}
          <p className={(m.attachments || []).some((a) => a.type === "audio") ? "text-xs text-foreground/80" : ""}>{m.text}</p>
        </div>
        <div className={`mt-2 flex ${mine ? "justify-end" : ""}`}><Attachments atts={(m.attachments || []).filter((a) => a.type === "product" || a.type === "khqr")} prefix={`message-${m.role}`} onMarkPaid={onMarkPaid} /></div>
      </div>
    </div>
  );
};

const QuickReplies = ({ items, onSend, disabled }) => (
  <div className="flex gap-2 overflow-x-auto pb-1" data-testid="quick-replies">
    <span className="shrink-0 self-center text-[10px] font-mono uppercase tracking-widest text-muted-foreground/80 flex items-center gap-1"><Zap className="h-3 w-3" />Quick</span>
    {items.map((q, i) => (
      <button key={i} onClick={() => onSend(q.text)} disabled={disabled} title={q.text} data-testid={`quick-reply-${i}`}
        className="shrink-0 rounded-full border border-indigo-400/30 bg-indigo-500/10 text-indigo-700 dark:text-indigo-200 px-3 py-1.5 text-xs font-medium hover:bg-indigo-500/25 transition-colors disabled:opacity-50">{q.label}</button>
    ))}
  </div>
);

const Composer = ({ conv, onSent, quick }) => {
  const [text, setText] = useState("");
  const [sugs, setSugs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);

  useEffect(() => { setSugs([]); setText(""); }, [conv.id]);

  const suggest = async () => {
    setLoading(true);
    try {
      const { data } = await api.post(`/conversations/${conv.id}/suggest`);
      setSugs(data.suggestions);
    } catch (e) { toast.error(errMsg(e)); } finally { setLoading(false); }
  };
  const send = async (t = text) => {
    if (!t.trim()) return;
    setSending(true);
    try {
      await api.post(`/conversations/${conv.id}/reply`, { text: t });
      setText(""); setSugs([]); onSent();
    } catch (e) { toast.error(errMsg(e)); } finally { setSending(false); }
  };

  return (
    <div className="border-t border-border/60 p-4 space-y-3 bg-surface">
      {quick.length > 0 && <QuickReplies items={quick} onSend={send} disabled={sending} />}
      <div className="flex flex-wrap gap-2 items-start">
        <button onClick={suggest} disabled={loading} data-testid="ai-suggest-btn"
          className="inline-flex items-center gap-1.5 rounded-full bg-amber-400/10 text-amber-700 dark:text-amber-300 border border-amber-400/30 px-3 py-1.5 text-xs font-semibold hover:bg-amber-400/20 transition-colors disabled:opacity-60">
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />} Suggest replies
        </button>
        {sugs.map((s, i) => (
          <button key={i} onClick={() => setText(s)} onDoubleClick={() => send(s)} data-testid={`ai-suggestion-${i}`} title="Click to edit · double-click to send"
            className="text-left rounded-xl border border-border bg-muted/50 px-3 py-2 text-xs leading-snug text-foreground hover:border-emerald-500/50 transition-colors max-w-xs">{s}</button>
        ))}
      </div>
      <div className="flex gap-2 items-end">
        <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} placeholder="Write a reply… (Enter to send)" data-testid="reply-input"
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} className="resize-none bg-muted/50" />
        <button onClick={() => send()} disabled={sending} data-testid="send-reply-btn"
          className="h-11 w-11 shrink-0 rounded-full btn-brand grid place-items-center transition-colors disabled:opacity-50">
          <ArrowUp className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

const ChatView = ({ conv, onBack, onChange, quick }) => {
  const [msgs, setMsgs] = useState([]);
  const [summary, setSummary] = useState(conv.summary || null);
  const [sumLoading, setSumLoading] = useState(false);
  const end = useRef(null);

  const loadSummary = async (force = false) => {
    setSumLoading(true);
    try {
      const { data } = await api.post(`/conversations/${conv.id}/summary`, null, { params: { force } });
      setSummary(data);
    } catch (e) { if (force) toast.error(errMsg(e)); } finally { setSumLoading(false); }
  };
  useEffect(() => { setSummary(conv.summary || null); }, [conv.id]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!msgs.length) return;
    const t = setTimeout(() => loadSummary(), 1500);
    return () => clearTimeout(t);
  }, [msgs.length, conv.id]);  // eslint-disable-line react-hooks/exhaustive-deps
  const load = () => api.get(`/conversations/${conv.id}/messages`).then((r) => setMsgs(r.data));
  const markPaid = async (orderId) => {
    try { await api.post(`/orders/${orderId}/mark-paid`); toast.success("Marked as paid — the customer was told"); load(); } catch (e) { toast.error(errMsg(e)); }
  };

  useEffect(() => {
    load();
    api.patch(`/conversations/${conv.id}`, { unread: 0 });
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conv.id]);
  useEffect(() => { const el = end.current; if (el) el.scrollTop = el.scrollHeight; }, [msgs.length]);

  const toggleAI = async (v) => {
    try {
      const { data } = await api.patch(`/conversations/${conv.id}`, { ai_enabled: v });
      onChange(data);
      toast.success(v ? "AI auto-reply on for this chat" : "You took over this chat");
    } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div className="flex h-full min-w-0">
    <div className="flex flex-col h-full min-w-0 flex-1" data-testid="chat-view">
      <div className="flex items-center gap-3 px-5 h-16 shrink-0 border-b border-border/60">
        <button onClick={onBack} className="md:hidden text-muted-foreground" data-testid="chat-back-btn"><ArrowLeft className="h-5 w-5" /></button>
        <div className="flex-1 min-w-0">
          <p className="font-semibold truncate" data-testid="chat-contact-name">{conv.name}</p>
          <ChannelBadge channel={conv.channel} />
        </div>
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <Bot className={`h-4 w-4 ${conv.ai_enabled ? "text-emerald-600 dark:text-emerald-400" : ""}`} />
          <span className="hidden sm:inline">AI auto-reply</span>
          <Switch checked={conv.ai_enabled} onCheckedChange={toggleAI} data-testid="ai-toggle-switch" />
        </label>
      </div>
      <SummaryStrip summary={summary} loading={sumLoading} />
      <div ref={end} className="flex-1 overflow-y-auto p-5 space-y-4">
        {msgs.map((m) => <Bubble key={m.id} m={m} onMarkPaid={markPaid} />)}
      </div>
      <Composer conv={conv} onSent={load} quick={quick} />
    </div>
    <SummaryPanel summary={summary} loading={sumLoading} onRefresh={() => loadSummary(true)} />
    </div>
  );
};

export default function Inbox() {
  const [convs, setConvs] = useState([]);
  const [active, setActive] = useState(null);
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");
  const [dq, setDq] = useState("");
  const [quick, setQuick] = useState([]);
  const [older, setOlder] = useState([]);
  const [olderMore, setOlderMore] = useState(null);
  const [firstMore, setFirstMore] = useState(false);
  const [total, setTotal] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const listRef = useRef(null);
  const gen = useRef(0);

  useEffect(() => { const t = setTimeout(() => setDq(q), 300); return () => clearTimeout(t); }, [q]);
  const params = { channel: filter, q: dq || undefined };
  const merged = useMemo(() => {
    const seen = new Set();
    return [...convs, ...older].filter((c) => !seen.has(c.id) && seen.add(c.id));
  }, [convs, older]);
  const hasMore = olderMore === null ? firstMore : olderMore;

  const loadMore = async () => {
    const last = merged[merged.length - 1];
    if (!last) return;
    const g = gen.current;
    setLoadingMore(true);
    try {
      const { data } = await api.get("/conversations", { params: { ...params, before: last.updated_at, before_id: last.id } });
      if (g !== gen.current) return;
      setOlder((o) => [...o, ...data.items]);
      setOlderMore(data.has_more);
    } finally { setLoadingMore(false); }
  };

  useEffect(() => { api.get("/settings").then((r) => setQuick((r.data.quick_replies || []).filter((x) => x.label && x.text))); }, []);

  useEffect(() => {
    gen.current += 1;
    setOlder([]);
    setOlderMore(null);
    if (listRef.current) listRef.current.scrollTop = 0;
    const load = () => api.get("/conversations", { params }).then((r) => {
      setConvs(r.data.items);
      setFirstMore(r.data.has_more);
      setTotal(r.data.total);
    });
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [filter, dq]);  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="h-full grid grid-cols-1 md:grid-cols-[340px_minmax(0,1fr)] overflow-hidden">
      <div className={`${active ? "hidden md:block" : ""} min-h-0 min-w-0 overflow-hidden`}>
        <ConvList convs={merged} active={active} onPick={setActive} filter={filter} setFilter={setFilter} q={q} setQ={setQ} total={total} hasMore={hasMore} onMore={loadMore} loadingMore={loadingMore} listRef={listRef} />
      </div>
      <div className={`${active ? "" : "hidden md:grid place-items-center"} min-h-0 min-w-0 h-full`}>
        {active ? <ChatView conv={active} onBack={() => setActive(null)} onChange={setActive} quick={quick} />
          : <p className="text-muted-foreground/80 text-sm" data-testid="no-chat-selected">Select a conversation to view it</p>}
      </div>
    </div>
  );
}
