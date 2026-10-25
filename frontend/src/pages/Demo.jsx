import { useEffect, useRef, useState } from "react";
import { ArrowLeft, MoreVertical, CheckCheck, Play, Pause, Images, Mic, Volume2, QrCode, BadgeCheck, RotateCcw, Zap, Paperclip, Smile } from "lucide-react";

const TEE = "https://images.unsplash.com/photo-1620799139507-2a76f79a2f4d?crop=entropy&cs=srgb&fm=jpg&q=80&w=500";
const OVERSIZE = "https://images.unsplash.com/photo-1622445275463-afa2ab738c34?crop=entropy&cs=srgb&fm=jpg&q=80&w=500";
const KM = { fontFamily: "'Noto Sans Khmer', 'Manrope', sans-serif" };

const VIDEO = new URLSearchParams(window.location.search).get("video") === "1";
const VOICE = (name) => `/demo/voice/${name}.mp3`;

// `say` = narrator line (video mode only); `play` = chat voice note; `vwait` = wait used in video mode.
const SCRIPT = [
  { say: "n1" },
  { wait: 700, vwait: 300, msg: { from: "me", text: "សួស្តីបង! មានអាវយឺតពណ៌ស ទំហំ M ទេ?", t: "23:04" } },
  { wait: 400, typing: 1700 },
  { msg: { from: "bot", album: [TEE, OVERSIZE], caption: "អាវយឺតកប្បាស ពណ៌ស — 8$\nអាវយឺតធំទូលាយ ពណ៌ស — 10$", t: "23:04" } },
  { wait: 200, note: [Images, "បង្ហាញរូបទំនិញដោយស្វ័យប្រវត្តិ"] },
  { say: "n2" },
  { wait: 1100, vwait: 300, typing: 1500 },
  { msg: { from: "bot", text: "មានបង! ទំហំ M នៅមានស្តុកទាំងពីរម៉ូដ។ អាវយឺតកប្បាស 8$ និងអាវយឺតធំទូលាយ 10$ ។ បងចូលចិត្តមួយណាដែរ?", t: "23:04" } },
  { wait: 2800, vwait: 1800, say: "n3" },
  { vwait: 300, msg: { from: "me", voice: "c1", dur: 3, t: "23:05" }, play: true, note: [Mic, "ស្ដាប់យល់សារជាសំឡេងខ្មែរ"] },
  { wait: 300, typing: 1800, recording: true },
  { msg: { from: "bot", voice: "c2", dur: 7, t: "23:05" }, play: true, note: [Volume2, "ឆ្លើយតបវិញជាសំឡេង"] },
  { wait: 300, msg: { from: "bot", text: "ចាស បង! អាវយឺតកប្បាសពណ៌ស ទំហំ M × ២ សរុប 16$ ។ សូមស្កេន KHQR ខាងក្រោម ដើម្បីទូទាត់។", t: "23:05" } },
  { wait: 1000, msg: { from: "bot", khqr: "/demo/khqr-16.png", caption: "KHQR · 16$ · ស្កេនបានក្នុងរយៈពេល ១០ នាទី", t: "23:05" } },
  { wait: 200, note: [QrCode, "ផ្ញើ KHQR តាមចំនួនទឹកប្រាក់ពិតប្រាកដ"] },
  { say: "n4" },
  { wait: 3800, vwait: 600, msg: { from: "bot", text: "បានទទួលការទូទាត់ ✅ សូមអរគុណ! ការកម្ម៉ង់ RF-8C21A9E4 · 16$ ត្រូវបានបញ្ជាក់។", t: "23:06" } },
  { wait: 200, note: [BadgeCheck, "បញ្ជាក់ការទូទាត់ដោយស្វ័យប្រវត្តិ"] },
  { wait: 2000, msg: { from: "me", text: "អរគុណច្រើនបង!", t: "23:06" } },
  { wait: 2600, vwait: 1800, end: true },
  { say: "n5" },
  { vwait: 1500 },
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const mmss = (s) => `0:${String(Math.round(s)).padStart(2, "0")}`;

const Stamp = ({ t, read }) => (
  <span className="float-right ml-2.5 mt-2 text-[10px] text-slate-400/80 inline-flex items-center gap-0.5">{t}{read && <CheckCheck className="h-3 w-3 text-sky-300" />}</span>
);

const Wave = ({ playing, mine }) => (
  <span className="flex items-end gap-[2px] h-6">
    {[6, 12, 18, 9, 20, 14, 7, 16, 22, 11, 17, 8, 13, 19, 10, 15, 6, 12, 18, 9].map((h, i) => (
      <span key={i} className={`w-[3px] rounded-full ${mine ? "bg-sky-200/80" : "bg-sky-400/80"} ${playing ? "demo-wave" : ""}`} style={{ height: h, animationDelay: `${i * 60}ms` }} />
    ))}
  </span>
);

const Voice = ({ m, playing }) => (
  <div className="flex items-center gap-2.5 pr-1">
    <span className={`h-10 w-10 shrink-0 rounded-full grid place-items-center ${m.from === "me" ? "bg-white text-[#2B5278]" : "bg-sky-500 text-white"}`}>
      {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 ml-0.5" />}
    </span>
    <div><Wave playing={playing} mine={m.from === "me"} /><p className="text-[11px] text-slate-300 mt-0.5">{mmss(m.dur)}</p></div>
  </div>
);

const Bubble = ({ m, playing }) => {
  const me = m.from === "me";
  const media = m.album || m.khqr;
  return (
    <div className={`flex ${me ? "justify-end" : ""} demo-pop`} data-testid={`demo-msg-${me ? "me" : "bot"}`}>
      <div className={`${m.khqr ? "w-[58%]" : media ? "w-[78%]" : "max-w-[82%]"} rounded-2xl ${me ? "rounded-br-md bg-[#2B5278]" : "rounded-bl-md bg-[#182533]"} overflow-hidden text-[14px] leading-relaxed text-white`}>
        {m.album && <div className="grid grid-cols-2 gap-0.5">{m.album.map((src) => <img key={src} src={src} alt="" className="h-36 w-full object-cover" />)}</div>}
        {m.khqr && <img src={m.khqr} alt="KHQR" className="w-full aspect-[2/3]" />}
        <div className="px-3 py-2">
          {m.voice ? <Voice m={m} playing={playing} /> : <span className="whitespace-pre-line">{m.text || m.caption}</span>}
          <Stamp t={m.t} read={me} />
        </div>
      </div>
    </div>
  );
};

const Typing = () => (
  <div className="flex demo-pop" data-testid="demo-typing">
    <div className="rounded-2xl rounded-bl-md bg-[#182533] px-4 py-3 flex gap-1">
      {[0, 1, 2].map((i) => <span key={i} className="h-2 w-2 rounded-full bg-slate-400 demo-dot" style={{ animationDelay: `${i * 150}ms` }} />)}
    </div>
  </div>
);

const Note = ({ note }) => {
  const [Icon, text] = note;
  return (
    <div className="absolute left-1/2 top-[76px] z-20 -translate-x-1/2 demo-note" data-testid="demo-note">
      <span className="flex items-center gap-2 whitespace-nowrap rounded-full bg-emerald-500 px-4 py-2 text-[13px] font-semibold text-slate-950 shadow-[0_10px_30px_rgba(16,185,129,0.45)]"><Icon className="h-4 w-4" />{text}</span>
    </div>
  );
};

const Header = ({ status }) => (
  <div className="relative z-10 flex items-center gap-3 bg-[#17212B] px-4 py-3 border-b border-black/30">
    <ArrowLeft className="h-5 w-5 text-slate-300" />
    <span className="h-10 w-10 rounded-full bg-gradient-to-br from-pink-400 to-rose-600 grid place-items-center text-sm font-bold text-white">រ</span>
    <div className="flex-1 min-w-0">
      <p className="text-[15px] font-semibold text-white truncate">ហាងសម្លៀកបំពាក់ រស្មី</p>
      <p className="text-[12px] text-sky-300" data-testid="demo-status">{status}</p>
    </div>
    <MoreVertical className="h-5 w-5 text-slate-300" />
  </div>
);

const Composer = () => (
  <div className="flex items-center gap-3 bg-[#17212B] px-4 py-3">
    <Smile className="h-5 w-5 text-slate-500" /><p className="flex-1 text-[14px] text-slate-500">សារ</p><Paperclip className="h-5 w-5 text-slate-500" /><Mic className="h-5 w-5 text-slate-500" />
  </div>
);

const FEATURES = [[Zap, "ឆ្លើយភ្លាមៗ ជាភាសាខ្មែរ ២៤ ម៉ោង"], [Mic, "ស្ដាប់ និងឆ្លើយជាសំឡេង"], [Images, "បង្ហាញរូបទំនិញដោយខ្លួនឯង"], [QrCode, "ទទួលប្រាក់តាម KHQR"]];

const Overlay = ({ end, onStart }) => (
  <div className={`absolute inset-0 z-30 flex flex-col px-7 demo-fade ${end || VIDEO ? "justify-center bg-[#0B0F17]" : "justify-end pb-14 bg-gradient-to-t from-[#0B0F17] via-[#0B0F17]/95 to-[#0B0F17]/60"}`} data-testid={end ? "demo-end" : "demo-intro"}>
    <p className="flex items-center gap-2 text-emerald-400 font-display font-bold text-lg"><span className="h-8 w-8 rounded-lg bg-emerald-500 text-slate-950 grid place-items-center"><Zap className="h-4 w-4" /></span>ReplyFlow</p>
    <h1 className="mt-5 text-[30px] font-bold leading-[1.35] text-white">{end ? "ឆ្លើយសារ បង្ហាញទំនិញ ទទួលប្រាក់ — ដោយស្វ័យប្រវត្តិ" : "អតិថិជនផ្ញើសារ ម៉ោង ១១ យប់?"}</h1>
    <p className="mt-3 text-[16px] leading-relaxed text-slate-300">{end ? "AI ជួយលក់ជំនួសអ្នក លើ Telegram និង Messenger" : "AI ឆ្លើយជំនួសអ្នកភ្លាមៗ ជាភាសាខ្មែរ ទាំងអក្សរ និងសំឡេង"}</p>
    {end && <ul className="mt-6 space-y-3">{FEATURES.map(([Icon, t], i) => (
      <li key={t} className="flex items-center gap-3 text-[15px] text-slate-100 demo-pop" style={{ animationDelay: `${0.2 + i * 0.15}s` }}><span className="h-9 w-9 rounded-full bg-emerald-500/15 text-emerald-400 grid place-items-center"><Icon className="h-4 w-4" /></span>{t}</li>
    ))}</ul>}
    {!VIDEO && <button type="button" onClick={onStart} data-testid={end ? "demo-replay-btn" : "demo-start-btn"}
      className="mt-8 inline-flex items-center justify-center gap-2 rounded-full bg-emerald-500 px-7 py-4 text-[16px] font-bold text-slate-950 active:scale-[0.98] transition-transform">
      {end ? <><RotateCcw className="h-5 w-5" /> មើលម្ដងទៀត</> : <><Play className="h-5 w-5" /> ចាប់ផ្ដើម</>}
    </button>}
    {!end && !VIDEO && <p className="mt-4 text-center text-[13px] text-slate-500">បើកការថតអេក្រង់ជាមុនសិន រួចចុច «ចាប់ផ្ដើម»</p>}
  </div>
);

const playAudio = (src, fallbackSec) => new Promise((resolve) => {
  const a = new Audio(src);
  const done = () => resolve();
  a.onended = done;
  a.onerror = () => setTimeout(done, fallbackSec * 1000);
  a.play().catch(() => setTimeout(done, fallbackSec * 1000));
});

const cue = (name) => console.log(`CUE ${name} ${Date.now()}`); // read by scripts/make_demo_video.py

const useScript = (timeline) => {
  const [msgs, setMsgs] = useState([]);
  const [typing, setTyping] = useState(null);
  const [note, setNote] = useState(null);
  const [playing, setPlaying] = useState(-1);
  const [phase, setPhase] = useState("intro");
  const run = useRef(0);
  const start = async () => {
    const id = ++run.current;
    setMsgs([]); setNote(null); setTyping(null); setPhase(VIDEO ? "intro" : "playing");
    if (VIDEO) cue("START");
    let count = 0;
    for (const step of SCRIPT) {
      if (step.say && !VIDEO) continue;
      await sleep((VIDEO ? step.vwait ?? step.wait : step.wait) || 0);
      if (run.current !== id) return;
      if (step.say) { cue(step.say); await sleep((timeline[step.say] || 2) * 1000 + 350); if (step.say === "n1") setPhase("playing"); continue; }
      if (step.typing) { setTyping(step.recording ? "rec" : "type"); await sleep(step.typing); setTyping(null); }
      if (step.note) { setNote(step.note); setTimeout(() => run.current === id && setNote((n) => (n === step.note ? null : n)), 2300); }
      if (step.msg) {
        const idx = count++;
        setMsgs((m) => [...m, step.msg]);
        if (step.play) {
          setPlaying(idx);
          if (VIDEO) { cue(step.msg.voice); await sleep((timeline[step.msg.voice] || step.msg.dur) * 1000 + 250); } else await playAudio(VOICE(step.msg.voice), step.msg.dur);
          if (run.current !== id) return;
          setPlaying(-1);
        }
      }
      if (step.end) setPhase("end");
    }
    if (VIDEO) cue("DONE");
  };
  useEffect(() => () => { run.current += 1; }, []);
  return { msgs, typing, note, playing, phase, start };
};

export default function Demo() {
  const [timeline, setTimeline] = useState(null);
  const { msgs, typing, note, playing, phase, start } = useScript(timeline || {});
  useEffect(() => { if (VIDEO) fetch("/demo/voice/timeline.json").then((r) => r.json()).then(setTimeline).catch(() => setTimeline({})); }, []);
  useEffect(() => { if (VIDEO && timeline) setTimeout(start, 1500); }, [timeline]); // eslint-disable-line react-hooks/exhaustive-deps
  const scroller = useRef(null);
  useEffect(() => { scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" }); }, [msgs, typing]);
  useEffect(() => { [TEE, OVERSIZE, "/demo/khqr-16.png"].forEach((src) => { new Image().src = src; }); }, []);
  const status = typing === "rec" ? "កំពុងថតសំឡេង…" : typing ? "កំពុងសរសេរ…" : "បូត · ឆ្លើយតបភ្លាមៗ";
  return (
    <div className={VIDEO ? "select-none" : "min-h-[100dvh] select-none bg-[#05070b] md:grid md:place-items-center md:py-6"} style={VIDEO ? { ...KM, zoom: 2.5 } : KM} data-testid="demo-page">
      <div className={VIDEO ? "relative flex h-[768px] w-[432px] flex-col overflow-hidden bg-[#0E1621]"
        : "relative mx-auto flex h-[100dvh] w-full flex-col overflow-hidden bg-[#0E1621] md:h-[min(844px,calc(100dvh-48px))] md:w-[390px] md:rounded-[44px] md:border-[10px] md:border-[#1c2230] md:shadow-2xl"}>
        <Header status={status} />
        {note && <Note note={note} key={note[1]} />}
        <div ref={scroller} className="flex-1 overflow-y-auto space-y-2.5 px-3 py-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          style={{ backgroundImage: "radial-gradient(rgba(255,255,255,0.035) 1px, transparent 1px)", backgroundSize: "18px 18px" }}>
          <p className="mx-auto w-fit rounded-full bg-black/30 px-3 py-1 text-[12px] text-slate-300">ថ្ងៃនេះ</p>
          {msgs.map((m, i) => <Bubble key={i} m={m} playing={playing === i} />)}
          {typing && <Typing />}
        </div>
        <Composer />
        {phase !== "playing" && <Overlay end={phase === "end"} onStart={start} />}
      </div>
    </div>
  );
}
