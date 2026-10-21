import { useEffect, useRef, useState } from "react";
import { MessageCircle, X, ArrowUp, Mic, Trash2 } from "lucide-react";
import { api, errMsg } from "@/lib/auth";
import { useRecorder, blobName, clock } from "@/lib/recorder";
import { Attachments, AudioAtt } from "@/components/Attachments";

const sessionId = (bid) => {
  const key = `rf_web_session_${bid}`;
  let s = localStorage.getItem(key);
  if (!s) {
    s = `web-${crypto.randomUUID()}`;
    localStorage.setItem(key, s);
  }
  return s;
};

export const Typing = () => (
  <div className="flex gap-1 px-3 py-2.5 bg-slate-800/80 rounded-2xl rounded-bl-sm w-fit" data-testid="typing-indicator">
    {[0, 1, 2].map((i) => <span key={i} className="dot h-1.5 w-1.5 rounded-full bg-emerald-400" />)}
  </div>
);

export const ChatPanel = ({ className = "", onClose, visitorName = "Website visitor", businessId = "default" }) => {
  const [info, setInfo] = useState({ business_name: "", greeting: "" });
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [missing, setMissing] = useState(false);
  const end = useRef(null);
  const sid = useRef(sessionId(businessId));
  const rec = useRecorder();

  const load = () => api.get(`/public/${businessId}/chat/${sid.current}`).then((r) => setMsgs(r.data.messages)).catch(() => {});

  useEffect(() => {
    let t;
    api.get(`/public/${businessId}/info`).then((r) => {
      setInfo(r.data);
      load();
      t = setInterval(load, 5000);
    }).catch(() => setMissing(true));
    return () => clearInterval(t);
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { const el = end.current; if (el) el.scrollTop = el.scrollHeight; }, [msgs, busy]);

  if (missing) return (
    <div className={`grid place-items-center bg-[#0F1522] border border-white/10 rounded-2xl text-sm text-slate-400 p-6 text-center ${className}`} data-testid="chat-unavailable">
      This chat is not available right now.
    </div>
  );

  const send = async (e) => {
    e.preventDefault();
    const t = text.trim();
    if (!t || busy) return;
    setText("");
    setMsgs((m) => [...m, { id: `tmp-${Date.now()}`, role: "user", text: t }]);
    setBusy(true);
    try {
      await api.post(`/public/${businessId}/chat`, { session_id: sid.current, text: t, name: visitorName });
      await load();
    } catch (e) {
      const text = e?.response?.status === 429 ? errMsg(e) : "Sorry, something went wrong. Please try again.";
      setMsgs((m) => [...m, { id: `err-${Date.now()}`, role: "ai", text }]);
    } finally {
      setBusy(false);
    }
  };

  const waitForReply = async (base, aiReply) => {
    for (let i = 0; i < 45; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      const { data } = await api.get(`/public/${businessId}/chat/${sid.current}`);
      const last = data.messages[data.messages.length - 1];
      if (data.messages.length >= base + (aiReply ? 2 : 1) && (!aiReply || last?.role !== "user")) return setMsgs(data.messages);
    }
    await load();
  };

  const sendVoice = async () => {
    const blob = await rec.stop();
    if (!blob || blob.size < 1200) return;
    setMsgs((m) => [...m, { id: `tmp-${Date.now()}`, role: "user", text: "Voice message", attachments: [{ type: "audio", url: URL.createObjectURL(blob) }] }]);
    setBusy(true);
    const fd = new FormData();
    fd.append("session_id", sid.current);
    fd.append("name", visitorName);
    fd.append("file", blob, blobName(blob));
    try {
      const base = (await api.get(`/public/${businessId}/chat/${sid.current}`)).data.messages.length;
      const { data: sent } = await api.post(`/public/${businessId}/voice`, fd);
      await waitForReply(base, sent.ai_reply);
    } catch (e) {
      const text = e?.response?.status === 429 ? errMsg(e) : "Sorry, I couldn't hear that. Please try again.";
      setMsgs((m) => [...m, { id: `err-${Date.now()}`, role: "ai", text }]);
    } finally {
      setBusy(false);
    }
  };

  const startRec = async () => {
    try { await rec.start(); } catch { setMsgs((m) => [...m, { id: `err-${Date.now()}`, role: "ai", text: "Please allow microphone access to send a voice message." }]); }
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
        {msgs.map((m) => {
          const mine = m.role === "user";
          const voice = (m.attachments || []).some((a) => a.type === "audio");
          return (
            <div key={m.id} className={`flex flex-col gap-1.5 ${mine ? "items-end" : "items-start"}`}>
              <div className={`px-3.5 py-2.5 max-w-[85%] rounded-2xl whitespace-pre-wrap space-y-1.5 ${mine ? "bg-emerald-500 text-slate-950 rounded-br-sm font-medium" : "bg-slate-800/80 rounded-bl-sm"}`}
                data-testid={`chat-msg-${m.role}`}>
                {(m.attachments || []).filter((a) => a.type === "audio").map((a, i) => <AudioAtt key={i} a={a} testid={`chat-msg-${m.role}-audio`} />)}
                <p className={voice ? "text-xs opacity-80" : ""}>{m.text}</p>
              </div>
              <Attachments atts={(m.attachments || []).filter((a) => a.type === "product")} prefix={`chat-msg-${m.role}`} />
            </div>
          );
        })}
        {busy && <Typing />}
      </div>
      {rec.recording ? (
        <div className="p-3 border-t border-white/10 flex items-center gap-3" data-testid="chat-recording-bar">
          <span className="h-2.5 w-2.5 rounded-full bg-red-500 animate-pulse" />
          <span className="flex-1 text-sm text-slate-300 font-mono">Recording {clock(rec.seconds)}</span>
          <button onClick={() => rec.stop()} data-testid="chat-voice-cancel-btn" className="h-10 w-10 rounded-full border border-white/10 grid place-items-center text-slate-400 hover:text-white"><Trash2 className="h-4 w-4" /></button>
          <button onClick={sendVoice} data-testid="chat-voice-send-btn" className="h-10 w-10 rounded-full bg-emerald-500 text-slate-950 grid place-items-center hover:bg-emerald-400"><ArrowUp className="h-4 w-4" /></button>
        </div>
      ) : (
        <form onSubmit={send} className="p-3 border-t border-white/10 flex gap-2">
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Type or record a voice message…" data-testid="chat-input"
            className="flex-1 min-w-0 bg-slate-900 border border-white/10 rounded-full px-4 py-2.5 text-sm outline-none focus:border-emerald-500/60" />
          {text.trim() ? (
            <button type="submit" disabled={busy} data-testid="chat-send-btn"
              className="h-10 w-10 shrink-0 rounded-full bg-emerald-500 text-slate-950 grid place-items-center hover:bg-emerald-400 transition-colors disabled:opacity-50">
              <ArrowUp className="h-4 w-4" />
            </button>
          ) : (
            <button type="button" onClick={startRec} disabled={busy} data-testid="chat-mic-btn" title="Record a voice message"
              className="h-10 w-10 shrink-0 rounded-full bg-emerald-500 text-slate-950 grid place-items-center hover:bg-emerald-400 transition-colors disabled:opacity-50">
              <Mic className="h-4 w-4" />
            </button>
          )}
        </form>
      )}
    </div>
  );
};

export const ChatWidget = () => {
  const [open, setOpen] = useState(false);
  return (
    <div className="fixed bottom-5 right-5 z-50 hidden md:block">
      {open && <ChatPanel className="w-[calc(100vw-2.5rem)] sm:w-[370px] h-[520px] mb-3 rise" onClose={() => setOpen(false)} />}
      <button onClick={() => setOpen(!open)} data-testid="chat-widget-toggle"
        className="ml-auto h-14 w-14 rounded-full bg-emerald-500 text-slate-950 grid place-items-center shadow-[0_0_30px_rgba(16,185,129,0.45)] hover:scale-105 transition-transform">
        {open ? <X /> : <MessageCircle />}
      </button>
    </div>
  );
};
