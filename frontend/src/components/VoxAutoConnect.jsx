import { useEffect, useRef, useState } from "react";
import { Check, CheckCircle2, ChevronDown, Copy, ExternalLink, Loader2, XCircle, AlertTriangle, Clock } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/auth";
import { Input } from "@/components/ui/input";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

const COLAB = "https://colab.research.google.com/#create=true";

const TXT = {
  en: {
    title: "Seller’s own voice (optional)",
    note: "Khmer voice replies already work without this. This free setup lets the AI speak with the seller’s own voice (VoxCPM2).",
    s1: "Open Google Colab", s1d: "Click the button. The code is copied for you. Sign in with Google if asked.", s1b: "Open Google Colab", s1done: "Opened — code copied",
    s2: "Turn on the free GPU", s2d: "In Colab’s top menu click:",
    s3: "Paste and press ▶", s3d: "Click in the empty code box, press", s3d2: "then press the ▶ button on its left.",
    s4: "Wait 5–8 minutes — that’s all", s4d: "ReplyFlow connects and saves by itself. Keep the Colab tab open.",
    again: "Copy code again", copied: "Code copied — paste it in Colab", copyFail: "Could not copy. Use “Copy code again”.",
    connected: "Seller voice server connected and saved",
    later: "Colab turns off after about 12 hours. To start again, open the same Colab tab and press ▶ — it reconnects by itself. Meanwhile the normal Khmer voice is used.",
    next: "Last step: record the seller’s voice sample below (5–10 seconds), then press Save.",
    progress: ["Install", "Load model", "Connect", "Done"],
    stages: {
      waiting: "Waiting for Colab… press ▶ in Colab", started: "Colab started — checking the GPU…", gpu: "Checking the GPU…",
      no_gpu: "No GPU yet — do step 2, then press ▶ again", installing: "Installing (2–4 min)…", loading: "Loading the voice model (2–6 min)…",
      linking: "Almost done — connecting to ReplyFlow…", ready: "Connected ✅ Seller voice is on",
      offline: "Colab has stopped. Press ▶ in Colab again (the normal Khmer voice is used meanwhile).", error: "Something went wrong. Press ▶ in Colab again.",
    },
    advanced: "Advanced: Modal (always on) or enter a server by hand",
    modalTitle: "Modal — always on, $30 free credit / month",
    modalSteps: ["Create a free account at modal.com.", "Open Google Colab (no GPU needed), paste the line below and press ▶.", "Click the Modal sign-in link it shows and approve. ReplyFlow connects by itself (~5 min)."],
    manual: "Or enter a server by hand",
  },
  km: {
    title: "សំឡេងផ្ទាល់របស់អ្នកលក់ (ស្រេចចិត្ត)",
    note: "ការឆ្លើយតបជាសំឡេងខ្មែរ ដំណើរការរួចហើយ ទោះបីមិនរៀបចំផ្នែកនេះក៏ដោយ។ ការរៀបចំឥតគិតថ្លៃនេះ ធ្វើឲ្យ AI និយាយដោយសំឡេងផ្ទាល់របស់អ្នកលក់ (VoxCPM2)។",
    s1: "បើក Google Colab", s1d: "ចុចប៊ូតុងខាងក្រោម។ កូដនឹងត្រូវចម្លងឲ្យអ្នកដោយស្វ័យប្រវត្តិ។ ចូលគណនី Google ប្រសិនបើត្រូវការ។", s1b: "បើក Google Colab", s1done: "បានបើក — កូដត្រូវបានចម្លង",
    s2: "បើក GPU ឥតគិតថ្លៃ", s2d: "នៅម៉ឺនុយខាងលើរបស់ Colab ចុច៖",
    s3: "បិទភ្ជាប់ ហើយចុច ▶", s3d: "ចុចក្នុងប្រអប់កូដទទេ រួចចុច", s3d2: "បន្ទាប់មកចុចប៊ូតុង ▶ នៅខាងឆ្វេង។",
    s4: "រង់ចាំ ៥–៨ នាទី — រួចរាល់!", s4d: "ReplyFlow នឹងភ្ជាប់ និងរក្សាទុកដោយខ្លួនឯង។ សូមទុកផ្ទាំង Colab ឲ្យនៅបើក។",
    again: "ចម្លងកូដម្ដងទៀត", copied: "បានចម្លងកូដ — សូមបិទភ្ជាប់ក្នុង Colab", copyFail: "មិនអាចចម្លងបានទេ។ សូមប្រើ «ចម្លងកូដម្ដងទៀត»។",
    connected: "បានភ្ជាប់ម៉ាស៊ីនសំឡេងអ្នកលក់ និងរក្សាទុករួចរាល់",
    later: "Colab បិទដោយខ្លួនឯងក្រោយប្រហែល ១២ ម៉ោង។ ដើម្បីចាប់ផ្ដើមវិញ បើកផ្ទាំង Colab ដដែល ហើយចុច ▶ — វានឹងភ្ជាប់ឡើងវិញដោយខ្លួនឯង។ ក្នុងពេលនោះ ប្រព័ន្ធប្រើសំឡេងខ្មែរធម្មតាជំនួស។",
    next: "ជំហានចុងក្រោយ៖ ថតសំឡេងអ្នកលក់ខាងក្រោម (៥–១០ វិនាទី) រួចចុច Save។",
    progress: ["ដំឡើង", "ផ្ទុកម៉ូដែល", "ភ្ជាប់", "រួចរាល់"],
    stages: {
      waiting: "កំពុងរង់ចាំ Colab… សូមចុច ▶ នៅក្នុង Colab", started: "Colab បានចាប់ផ្ដើម — កំពុងពិនិត្យ GPU…", gpu: "កំពុងពិនិត្យ GPU…",
      no_gpu: "មិនទាន់មាន GPU — សូមធ្វើជំហានទី ២ រួចចុច ▶ ម្ដងទៀត", installing: "កំពុងដំឡើង (២–៤ នាទី)…", loading: "កំពុងផ្ទុកម៉ូដែលសំឡេង (២–៦ នាទី)…",
      linking: "ជិតរួចហើយ — កំពុងភ្ជាប់ទៅ ReplyFlow…", ready: "បានភ្ជាប់ ✅ សំឡេងអ្នកលក់បានបើក",
      offline: "Colab បានឈប់។ សូមចុច ▶ នៅក្នុង Colab ម្ដងទៀត (ក្នុងពេលនេះ ប្រើសំឡេងខ្មែរធម្មតា)។", error: "មានបញ្ហា។ សូមចុច ▶ នៅក្នុង Colab ម្ដងទៀត។",
    },
    advanced: "កម្រិតខ្ពស់៖ Modal (បើកជានិច្ច) ឬបញ្ចូលម៉ាស៊ីនមេដោយដៃ",
    modalTitle: "Modal — បើកជានិច្ច ឥតគិតថ្លៃ $30 / ខែ",
    modalSteps: ["បង្កើតគណនីឥតគិតថ្លៃនៅ modal.com។", "បើក Google Colab (មិនត្រូវការ GPU) បិទភ្ជាប់កូដខាងក្រោម ហើយចុច ▶។", "ចុចតំណចូល Modal ដែលវាបង្ហាញ ហើយយល់ព្រម។ ReplyFlow នឹងភ្ជាប់ដោយខ្លួនឯង (~៥ នាទី)។"],
    manual: "ឬបញ្ចូលម៉ាស៊ីនមេដោយដៃ",
  },
};

const STEP_OF = { waiting: -1, started: 0, gpu: 0, no_gpu: 0, installing: 0, loading: 1, linking: 2, ready: 4, offline: 4, error: -1 };
const BUSY = ["started", "gpu", "installing", "loading", "linking"];

const setupLine = (file, token) => `B="${window.location.origin}"; T="${token}"; import urllib.request as u; exec(u.urlopen(B+"/voxcpm/${file}").read())`;

const copyText = (text, t) => navigator.clipboard.writeText(text).then(() => toast.success(t.copied)).catch(() => toast.error(t.copyFail));

const usePair = (setS, t) => {
  const [p, setP] = useState(null);
  const prev = useRef(null);
  useEffect(() => {
    let timer, alive = true;
    const tick = async () => {
      try {
        const { data } = await api.get("/voice/voxcpm-pair");
        if (!alive) return;
        if (prev.current && prev.current !== "ready" && data.stage === "ready") {
          setS((x) => ({ ...x, voxcpm_url: data.url, voxcpm_key: data.key }));
          toast.success(t.connected);
        }
        prev.current = data.stage;
        setP(data);
      } catch { /* retry on next tick */ }
      if (alive) timer = setTimeout(tick, prev.current === "ready" ? 30000 : 4000);
    };
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [setS, t]);
  return p;
};

const Num = ({ n, done }) => (
  <span className={`shrink-0 h-8 w-8 rounded-full grid place-items-center text-sm font-bold transition-colors duration-300 ${done ? "bg-emerald-500 text-slate-950" : "bg-white/5 border border-white/15 text-slate-200"}`}>
    {done ? <Check className="h-4 w-4" /> : n}
  </span>
);

const Step = ({ n, title, done, children, testid }) => (
  <li className="flex gap-3 rounded-xl border border-white/10 bg-[#0B0F17] p-4 min-w-0" data-testid={testid}>
    <Num n={n} done={done} />
    <div className="flex-1 min-w-0 space-y-2 pt-1"><p className="text-sm font-semibold text-slate-100">{title}</p>{children}</div>
  </li>
);

const Chip = ({ children }) => <span className="rounded-md bg-slate-800 border border-white/10 px-2 py-1 text-[11px] font-mono text-slate-100">{children}</span>;
const Key = ({ children }) => <kbd className="rounded-md bg-slate-800 border-b-2 border-slate-600 px-2 py-0.5 text-[11px] font-mono text-slate-100">{children}</kbd>;

const Progress = ({ stage, t }) => {
  const at = STEP_OF[stage] ?? -1;
  return (
    <div className="grid grid-cols-4 gap-1.5" data-testid="vox-progress">
      {t.progress.map((label, i) => (
        <div key={label} className="space-y-1">
          <div className={`h-1.5 rounded-full transition-colors duration-500 ${i < at || at === 4 ? "bg-emerald-400" : i === at ? "bg-emerald-400/50 animate-pulse" : "bg-white/10"}`} />
          <p className="text-[10px] text-slate-500 truncate">{label}</p>
        </div>
      ))}
    </div>
  );
};

const TONE = { ready: "text-emerald-300", no_gpu: "text-amber-300", offline: "text-amber-300", error: "text-red-300", waiting: "text-slate-300" };

const StatusIcon = ({ stage }) => {
  if (BUSY.includes(stage)) return <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />;
  if (stage === "ready") return <CheckCircle2 className="h-4 w-4 text-emerald-400" />;
  if (stage === "error") return <XCircle className="h-4 w-4 text-red-400" />;
  if (stage === "waiting") return <Clock className="h-4 w-4 text-slate-400 animate-pulse" />;
  return <AlertTriangle className="h-4 w-4 text-amber-400" />;
};

const Status = ({ p, t }) => (
  <div className="rounded-lg border border-white/10 bg-slate-950/60 p-3 space-y-3" data-testid="vox-status">
    <p className={`flex items-start gap-2 text-sm font-medium ${TONE[p.stage] || "text-slate-200"}`} data-testid="vox-status-text">
      <span className="mt-0.5"><StatusIcon stage={p.stage} /></span>{t.stages[p.stage] || p.stage}
    </p>
    {p.stage === "ready" && p.gpu && <p className="text-[11px] font-mono text-slate-500" data-testid="vox-status-gpu">{p.source} · {p.gpu}</p>}
    {p.stage === "error" && p.error && <p className="text-[11px] font-mono text-red-300/80 break-words" data-testid="vox-status-error">{p.error}</p>}
    <Progress stage={p.stage} t={t} />
  </div>
);

const LangSwitch = ({ lang, setLang }) => (
  <div className="inline-flex rounded-full border border-white/10 p-0.5 text-[11px] font-semibold" data-testid="vox-lang-switch">
    {[["en", "EN"], ["km", "ខ្មែរ"]].map(([k, l]) => (
      <button key={k} type="button" onClick={() => setLang(k)} data-testid={`vox-lang-${k}`}
        className={`rounded-full px-3 py-1 transition-colors duration-200 ${lang === k ? "bg-emerald-500 text-slate-950" : "text-slate-400 hover:text-slate-200"}`}>{l}</button>
    ))}
  </div>
);

const Steps = ({ p, t }) => {
  const [opened, setOpened] = useState(false);
  const line = setupLine("colab_setup.py", p.token);
  const open = () => { copyText(line, t); window.open(COLAB, "_blank", "noopener"); setOpened(true); };
  const at = STEP_OF[p.stage] ?? -1;
  return (
    <ol className="space-y-2.5">
      <Step n={1} title={t.s1} done={opened || at >= 0} testid="vox-step-1">
        <p className="text-xs text-slate-400">{t.s1d}</p>
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" onClick={open} data-testid="vox-open-colab-btn"
            className="inline-flex items-center gap-2 rounded-full bg-emerald-500 text-slate-950 px-5 py-2.5 text-sm font-bold hover:bg-emerald-400 active:scale-[0.98] transition-transform duration-150">
            <ExternalLink className="h-4 w-4" /> {t.s1b}
          </button>
          {opened && <span className="text-xs text-emerald-400 flex items-center gap-1" data-testid="vox-opened-note"><Check className="h-3.5 w-3.5" /> {t.s1done}</span>}
        </div>
        <button type="button" onClick={() => copyText(line, t)} data-testid="vox-copy-again-btn" className="inline-flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-300 underline-offset-2 hover:underline">
          <Copy className="h-3 w-3" /> {t.again}
        </button>
      </Step>
      <Step n={2} title={t.s2} done={at > 0 || p.stage === "installing"} testid="vox-step-2">
        <p className="text-xs text-slate-400">{t.s2d}</p>
        <div className="flex flex-wrap items-center gap-1.5 text-slate-500 text-xs"><Chip>Runtime</Chip>›<Chip>Change runtime type</Chip>›<Chip>T4 GPU</Chip>›<Chip>Save</Chip></div>
      </Step>
      <Step n={3} title={t.s3} done={at >= 0} testid="vox-step-3">
        <p className="text-xs text-slate-400 leading-relaxed">{t.s3d} <Key>Ctrl</Key> + <Key>V</Key> <span className="text-slate-500">(Mac: <Key>⌘</Key> + <Key>V</Key>)</span>, {t.s3d2}</p>
      </Step>
      <Step n={4} title={t.s4} done={p.stage === "ready"} testid="vox-step-4">
        <p className="text-xs text-slate-400">{t.s4d}</p>
        <Status p={p} t={t} />
      </Step>
    </ol>
  );
};

const CheckConn = ({ s }) => {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const run = async () => {
    setBusy(true);
    try { setRes((await api.post("/voice/voxcpm-check", { url: s.voxcpm_url, key: s.voxcpm_key })).data); } catch (e) { setRes({ ok: false, error: errMsg(e) }); } finally { setBusy(false); }
  };
  return (
    <div className="flex flex-wrap items-center gap-3">
      <button type="button" onClick={run} disabled={busy || !s.voxcpm_url} data-testid="voxcpm-check-btn"
        className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold hover:bg-white/5 disabled:opacity-50">
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />} Check connection
      </button>
      {res && (res.ok
        ? <span className="text-xs text-emerald-400 flex items-center gap-1" data-testid="voxcpm-check-result"><CheckCircle2 className="h-3.5 w-3.5" /> Connected — VoxCPM2 on {res.gpu}</span>
        : <span className="text-xs text-red-400 flex items-center gap-1" data-testid="voxcpm-check-result"><XCircle className="h-3.5 w-3.5" /> {res.error}</span>)}
    </div>
  );
};

const Advanced = ({ s, setS, Field, p, t }) => {
  const line = setupLine("modal_setup.py", p.token);
  return (
    <Collapsible>
      <CollapsibleTrigger data-testid="vox-advanced-toggle" className="group flex w-full items-center justify-between rounded-lg px-1 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200">
        {t.advanced}<ChevronDown className="h-4 w-4 transition-transform duration-200 group-data-[state=open]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-4 pt-2" data-testid="vox-advanced-content">
        <div className="rounded-xl border border-white/10 bg-[#0B0F17] p-4 space-y-3 min-w-0" data-testid="guide-modal">
          <p className="text-sm font-semibold">{t.modalTitle}</p>
          <ol className="list-decimal pl-5 space-y-1.5 text-xs text-slate-300">{t.modalSteps.map((st) => <li key={st}>{st}</li>)}</ol>
          <div className="flex gap-2 min-w-0">
            <code className="flex-1 min-w-0 truncate rounded-lg bg-slate-950 border border-white/10 px-3 py-2 text-[11px] font-mono text-emerald-300" data-testid="guide-modal-line">{line}</code>
            <button type="button" onClick={() => copyText(line, t)} data-testid="guide-modal-line-copy" className="shrink-0 rounded-lg border border-white/10 px-3 hover:bg-white/5"><Copy className="h-4 w-4" /></button>
          </div>
        </div>
        <p className="text-xs font-semibold text-slate-400">{t.manual}</p>
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="VoxCPM2 server URL"><Input value={s.voxcpm_url} onChange={(e) => setS((x) => ({ ...x, voxcpm_url: e.target.value }))} placeholder="https://xxxx.trycloudflare.com or https://xxxx.modal.run" data-testid="voxcpm-url-input" /></Field>
          <Field label="API key (optional)"><Input type="password" value={s.voxcpm_key} onChange={(e) => setS((x) => ({ ...x, voxcpm_key: e.target.value }))} data-testid="voxcpm-key-input" /></Field>
        </div>
        <CheckConn s={s} />
      </CollapsibleContent>
    </Collapsible>
  );
};

export const VoxAutoConnect = ({ s, setS, Field }) => {
  const [lang, setLangState] = useState(() => localStorage.getItem("rf_setup_lang") || "en");
  const setLang = (l) => { localStorage.setItem("rf_setup_lang", l); setLangState(l); };
  const t = TXT[lang];
  const p = usePair(setS, t);
  return (
    <div className="border-t border-white/10 pt-4 space-y-4" data-testid="vox-auto-connect">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-sm" data-testid="vox-title">{t.title}</p>
          <p className="text-xs text-slate-400 mt-1 leading-relaxed">{t.note}</p>
        </div>
        <LangSwitch lang={lang} setLang={setLang} />
      </div>
      {!p ? <Loader2 className="h-4 w-4 animate-spin text-slate-500" data-testid="vox-loading" /> : <>
        <Steps p={p} t={t} />
        <p className="text-[11px] text-slate-500 leading-relaxed" data-testid="vox-later-note">{t.later}</p>
        {p.stage === "ready" && !s.seller_voice_media_id && <p className="text-xs text-amber-300" data-testid="vox-next-note">{t.next}</p>}
        <Advanced s={s} setS={setS} Field={Field} p={p} t={t} />
      </>}
    </div>
  );
};
