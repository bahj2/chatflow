import { useEffect, useRef, useState } from "react";
import { Search, Sparkles, ArrowUp, Bot, User, Headphones, ArrowLeft, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/auth";
import { ChannelBadge } from "@/components/ChannelBadge";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

const FILTERS = ["all", "web", "telegram", "messenger"];
const time = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "");

const ConvList = ({ convs, active, onPick, filter, setFilter, q, setQ }) => (
  <div className="flex flex-col h-full border-r border-white/5 bg-[#0D121C]">
    <div className="p-4 space-y-3 border-b border-white/5">
      <h1 className="font-display text-xl font-bold">Inbox</h1>
      <div className="relative">
        <Search className="h-4 w-4 absolute left-3 top-2.5 text-slate-500" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" data-testid="inbox-search-input"
          className="w-full bg-slate-900 border border-white/10 rounded-lg pl-9 pr-3 py-2 text-sm outline-none focus:border-emerald-500/60" />
      </div>
      <div className="flex gap-1">
        {FILTERS.map((f) => (
          <button key={f} onClick={() => setFilter(f)} data-testid={`filter-${f}`}
            className={`px-2.5 py-1 rounded-md text-xs font-medium capitalize transition-colors ${filter === f ? "bg-white text-slate-950" : "text-slate-400 hover:bg-white/5"}`}>{f}</button>
        ))}
      </div>
    </div>
    <div className="flex-1 overflow-y-auto" data-testid="conversation-list">
      {convs.length === 0 && <p className="p-6 text-sm text-slate-500" data-testid="inbox-empty">No conversations yet. Try the chat on your website!</p>}
      {convs.map((c) => (
        <button key={c.id} onClick={() => onPick(c)} data-testid={`conversation-item-${c.id}`}
          className={`w-full text-left px-4 py-3.5 border-b border-white/5 transition-colors ${active?.id === c.id ? "bg-emerald-500/[0.07] border-l-2 border-l-emerald-400" : "hover:bg-white/[0.03]"}`}>
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold text-sm truncate">{c.name}</span>
            <span className="text-[11px] text-slate-500 shrink-0">{time(c.updated_at)}</span>
          </div>
          <div className="flex items-center gap-2 mt-1.5">
            <ChannelBadge channel={c.channel} compact />
            <span className="text-xs text-slate-400 truncate flex-1">{c.last_message}</span>
            {c.unread > 0 && <span className="h-5 min-w-5 px-1.5 rounded-full bg-emerald-500 text-slate-950 text-[11px] font-bold grid place-items-center">{c.unread}</span>}
          </div>
        </button>
      ))}
    </div>
  </div>
);

const ROLE = {
  user: { Icon: User, label: "Customer", cls: "bg-slate-800/80 border-white/10" },
  ai: { Icon: Bot, label: "AI auto-reply", cls: "bg-emerald-500/[0.08] border-emerald-500/30" },
  agent: { Icon: Headphones, label: "You", cls: "bg-indigo-500/[0.1] border-indigo-500/30" },
};

const Bubble = ({ m }) => {
  const r = ROLE[m.role];
  const mine = m.role !== "user";
  return (
    <div className={`flex ${mine ? "justify-end" : ""}`} data-testid={`message-${m.role}`}>
      <div className="max-w-[75%]">
        <p className={`text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1 flex items-center gap-1 ${mine ? "justify-end" : ""}`}>
          <r.Icon className="h-3 w-3" />{r.label} · {time(m.created_at)}
        </p>
        <div className={`border rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap ${r.cls}`}>{m.text}</div>
      </div>
    </div>
  );
};

const Composer = ({ conv, onSent }) => {
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
    <div className="border-t border-white/5 p-4 space-y-3 bg-[#0D121C]">
      <div className="flex flex-wrap gap-2 items-center">
        <button onClick={suggest} disabled={loading} data-testid="ai-suggest-btn"
          className="inline-flex items-center gap-1.5 rounded-full bg-amber-400/10 text-amber-300 border border-amber-400/30 px-3 py-1.5 text-xs font-semibold hover:bg-amber-400/20 transition-colors disabled:opacity-60">
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />} Suggest replies
        </button>
        {sugs.map((s, i) => (
          <button key={i} onClick={() => setText(s)} onDoubleClick={() => send(s)} data-testid={`ai-suggestion-${i}`} title="Click to edit · double-click to send"
            className="text-left rounded-xl border border-white/10 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 hover:border-emerald-500/50 transition-colors max-w-xs line-clamp-2">{s}</button>
        ))}
      </div>
      <div className="flex gap-2 items-end">
        <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} placeholder="Write a reply… (Enter to send)" data-testid="reply-input"
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} className="resize-none bg-slate-900" />
        <button onClick={() => send()} disabled={sending} data-testid="send-reply-btn"
          className="h-11 w-11 shrink-0 rounded-full bg-emerald-500 text-slate-950 grid place-items-center hover:bg-emerald-400 transition-colors disabled:opacity-50">
          <ArrowUp className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

const ChatView = ({ conv, onBack, onChange }) => {
  const [msgs, setMsgs] = useState([]);
  const end = useRef(null);
  const load = () => api.get(`/conversations/${conv.id}/messages`).then((r) => setMsgs(r.data));

  useEffect(() => {
    load();
    api.patch(`/conversations/${conv.id}`, { unread: 0 });
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conv.id]);
  useEffect(() => { const el = end.current; if (el) el.scrollTop = el.scrollHeight; }, [msgs.length]);

  const toggleAI = async (v) => {
    const { data } = await api.patch(`/conversations/${conv.id}`, { ai_enabled: v });
    onChange(data);
    toast.success(v ? "AI auto-reply on for this chat" : "You took over this chat");
  };

  return (
    <div className="flex flex-col h-full min-w-0" data-testid="chat-view">
      <div className="flex items-center gap-3 px-5 h-16 border-b border-white/5">
        <button onClick={onBack} className="md:hidden text-slate-400" data-testid="chat-back-btn"><ArrowLeft className="h-5 w-5" /></button>
        <div className="flex-1 min-w-0">
          <p className="font-semibold truncate" data-testid="chat-contact-name">{conv.name}</p>
          <ChannelBadge channel={conv.channel} />
        </div>
        <label className="flex items-center gap-2 text-xs text-slate-400">
          <Bot className={`h-4 w-4 ${conv.ai_enabled ? "text-emerald-400" : ""}`} />
          <span className="hidden sm:inline">AI auto-reply</span>
          <Switch checked={conv.ai_enabled} onCheckedChange={toggleAI} data-testid="ai-toggle-switch" />
        </label>
      </div>
      <div ref={end} className="flex-1 overflow-y-auto p-5 space-y-4">
        {msgs.map((m) => <Bubble key={m.id} m={m} />)}
      </div>
      <Composer conv={conv} onSent={load} />
    </div>
  );
};

export default function Inbox() {
  const [convs, setConvs] = useState([]);
  const [active, setActive] = useState(null);
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");

  useEffect(() => {
    const load = () => api.get("/conversations", { params: { channel: filter, q: q || undefined } }).then((r) => setConvs(r.data));
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [filter, q]);

  return (
    <div className="h-full grid md:grid-cols-[340px_1fr]">
      <div className={`${active ? "hidden md:block" : ""} min-h-0`}>
        <ConvList convs={convs} active={active} onPick={setActive} filter={filter} setFilter={setFilter} q={q} setQ={setQ} />
      </div>
      <div className={`${active ? "" : "hidden md:grid"} min-h-0 place-items-center`}>
        {active ? <ChatView conv={active} onBack={() => setActive(null)} onChange={setActive} />
          : <p className="text-slate-500 text-sm" data-testid="no-chat-selected">Select a conversation to view it</p>}
      </div>
    </div>
  );
}
