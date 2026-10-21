import { useEffect, useRef, useState } from "react";
import { MessageCircle, X, ArrowUp } from "lucide-react";
import { api } from "@/lib/auth";

const sessionId = () => {
  let s = localStorage.getItem("rf_web_session");
  if (!s) {
    s = `web-${crypto.randomUUID()}`;
    localStorage.setItem("rf_web_session", s);
  }
  return s;
};

export const Typing = () => (
  <div className="flex gap-1 px-3 py-2.5 bg-slate-800/80 rounded-2xl rounded-bl-sm w-fit" data-testid="typing-indicator">
    {[0, 1, 2].map((i) => <span key={i} className="dot h-1.5 w-1.5 rounded-full bg-emerald-400" />)}
  </div>
);

export const ChatPanel = ({ className = "", onClose }) => {
  const [info, setInfo] = useState({ business_name: "", greeting: "" });
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef(null);
  const sid = useRef(sessionId());

  const load = () => api.get(`/public/chat/${sid.current}`).then((r) => setMsgs(r.data.messages));

  useEffect(() => {
    api.get("/public/info").then((r) => setInfo(r.data));
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => { const el = end.current; if (el) el.scrollTop = el.scrollHeight; }, [msgs, busy]);

  const send = async (e) => {
    e.preventDefault();
    const t = text.trim();
    if (!t || busy) return;
    setText("");
    setMsgs((m) => [...m, { id: `tmp-${Date.now()}`, role: "user", text: t }]);
    setBusy(true);
    try {
      await api.post("/public/chat", { session_id: sid.current, text: t });
      await load();
    } catch {
      setMsgs((m) => [...m, { id: `err-${Date.now()}`, role: "ai", text: "Sorry, something went wrong. Please try again." }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`flex flex-col bg-[#0F1522] border border-white/10 rounded-2xl overflow-hidden shadow-2xl ${className}`} data-testid="chat-panel">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-white/10 bg-[#111827]">
        <div className="h-9 w-9 rounded-full bg-emerald-500/15 grid place-items-center text-emerald-400 font-display font-bold">
          {(info.business_name || "A")[0]}
        </div>
        <div className="flex-1">
          <p className="font-display font-semibold text-sm" data-testid="chat-business-name">{info.business_name}</p>
          <p className="text-[11px] text-emerald-400 flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Replies instantly</p>
        </div>
        {onClose && <button onClick={onClose} data-testid="chat-close-btn" className="text-slate-400 hover:text-white"><X className="h-4 w-4" /></button>}
      </div>
      <div ref={end} className="flex-1 overflow-y-auto p-4 space-y-3 text-sm" data-testid="chat-messages">
        <div className="bg-slate-800/80 rounded-2xl rounded-bl-sm px-3.5 py-2.5 max-w-[85%]">{info.greeting}</div>
        {msgs.map((m) => (
          <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : ""}`}>
            <div className={`px-3.5 py-2.5 max-w-[85%] rounded-2xl whitespace-pre-wrap ${m.role === "user" ? "bg-emerald-500 text-slate-950 rounded-br-sm font-medium" : "bg-slate-800/80 rounded-bl-sm"}`}
              data-testid={`chat-msg-${m.role}`}>{m.text}</div>
          </div>
        ))}
        {busy && <Typing />}
      </div>
      <form onSubmit={send} className="p-3 border-t border-white/10 flex gap-2">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Type your message…" data-testid="chat-input"
          className="flex-1 bg-slate-900 border border-white/10 rounded-full px-4 py-2.5 text-sm outline-none focus:border-emerald-500/60" />
        <button type="submit" disabled={busy} data-testid="chat-send-btn"
          className="h-10 w-10 rounded-full bg-emerald-500 text-slate-950 grid place-items-center hover:bg-emerald-400 transition-colors disabled:opacity-50">
          <ArrowUp className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
};

export const ChatWidget = () => {
  const [open, setOpen] = useState(false);
  return (
    <div className="fixed bottom-5 right-5 z-50">
      {open && <ChatPanel className="w-[calc(100vw-2.5rem)] sm:w-[370px] h-[520px] mb-3 rise" onClose={() => setOpen(false)} />}
      <button onClick={() => setOpen(!open)} data-testid="chat-widget-toggle"
        className="ml-auto h-14 w-14 rounded-full bg-emerald-500 text-slate-950 grid place-items-center shadow-[0_0_30px_rgba(16,185,129,0.45)] hover:scale-105 transition-transform">
        {open ? <X /> : <MessageCircle />}
      </button>
    </div>
  );
};
