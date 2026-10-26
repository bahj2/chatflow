import { Link } from "react-router-dom";
import { ArrowRight, Send, Facebook, QrCode, Brain, Hand, Sparkles } from "lucide-react";
import { BrandMark, BRAND } from "@/components/Brand";
import { TelegramDemo } from "@/components/TelegramDemo";

const FEATURES = [
  { Icon: Send, color: "#229ED9", t: "Telegram bot", d: "Paste your BotFather token, click connect. Every message gets an instant reply." },
  { Icon: Facebook, color: "#0084FF", t: "Facebook Messenger", d: "Connect your Page and answer customers 24/7 — even while you sleep." },
  { Icon: QrCode, color: "#E11D48", t: "Bakong KHQR payments", d: "When a customer confirms an order, the AI sends a KHQR with the exact total. Pay with any Cambodian bank app." },
  { Icon: Brain, color: "#F59E0B", t: "Knows your business", d: "Teach it your products, prices and FAQs once. It understands what clients really mean." },
];

const STEPS = [
  ["01", "Describe your business", "Shop, services or anything else — add info, FAQs and pick a tone."],
  ["02", "Connect your channels", "Paste your Telegram bot token and connect your Facebook Page — all in one place."],
  ["03", "AI replies, you stay in control", "Take over any chat, or tap an AI-suggested reply to answer in one click."],
];

export default function Landing() {
  return (
    <div className="grain min-h-screen bg-[#0B0F17] text-slate-100 overflow-x-hidden">
      <nav className="sticky top-0 z-40 backdrop-blur-xl bg-[#0B0F17]/70 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2 font-display font-bold text-lg" data-testid="nav-logo">
            <BrandMark />
            {BRAND}
          </div>
          <div className="hidden md:flex gap-8 text-sm text-slate-400">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#how" className="hover:text-white transition-colors">How it works</a>
          </div>
          <div className="flex items-center gap-2">
            <Link to="/login" data-testid="nav-login-btn" className="px-4 py-2 text-sm font-semibold text-slate-300 hover:text-white">Log in</Link>
            <Link to="/signup" data-testid="nav-signup-btn"
              className="rounded-full bg-white text-slate-950 px-5 py-2 text-sm font-semibold hover:bg-emerald-400 transition-colors">
              Start free
            </Link>
          </div>
        </div>
      </nav>

      <section className="grid-bg relative">
        <div className="max-w-7xl mx-auto px-6 pt-20 pb-24 grid lg:grid-cols-[1.15fr_1fr] gap-14 items-start">
          <div className="rise lg:pt-24">
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-emerald-400 mb-6">Telegram · Messenger · Bakong KHQR</p>
            <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.05]">
              Every client message,<br />answered in <span className="text-emerald-400">seconds.</span>
            </h1>
            <p className="mt-6 text-base md:text-lg text-slate-400 max-w-xl leading-relaxed">
              ReplyFlow's AI understands what your customers want and replies instantly on all your channels — in their language, in your tone. Jump in anytime with one-tap suggested replies.
            </p>
            <div className="mt-10 flex flex-wrap gap-4">
              <Link to="/signup" data-testid="hero-get-started-btn"
                className="inline-flex items-center gap-2 rounded-full bg-emerald-500 text-slate-950 px-7 py-3.5 font-semibold shadow-[0_0_30px_rgba(16,185,129,0.35)] hover:bg-emerald-400 transition-colors">
                Create free account <ArrowRight className="h-4 w-4" />
              </Link>
              <a href="#how" data-testid="hero-how-btn" className="rounded-full border border-white/15 px-7 py-3.5 font-semibold hover:bg-white/5 transition-colors">How it works</a>
            </div>
            <div className="mt-12 flex gap-10 text-sm">
              {[["< 5s", "avg. reply"], ["24/7", "always on"], ["2", "channels"]].map(([a, b]) => (
                <div key={b}><p className="font-display text-2xl font-bold">{a}</p><p className="text-slate-500">{b}</p></div>
              ))}
            </div>
          </div>
          <div className="rise relative" style={{ animationDelay: "0.15s" }}>
            <div className="absolute -inset-6 bg-emerald-500/10 blur-3xl rounded-full" />
            <p className="relative font-mono text-[11px] uppercase tracking-widest text-slate-500 mb-3 flex items-center gap-2"><Sparkles className="h-3 w-3 text-emerald-400" /> Real example — a customer on Telegram</p>
            <TelegramDemo className="relative max-w-md mx-auto lg:mx-0" />
          </div>
        </div>
      </section>

      <section id="features" className="max-w-7xl mx-auto px-6 py-24">
        <h2 className="font-display text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight max-w-2xl">One AI brain. All the places your clients write to you.</h2>
        <div className="mt-14 grid sm:grid-cols-2 lg:grid-cols-4 gap-px bg-white/5 rounded-2xl overflow-hidden border border-white/5">
          {FEATURES.map(({ Icon, color, t, d }) => (
            <div key={t} className="bg-[#0F1522] p-8 hover:bg-[#121a2a] transition-colors" data-testid={`feature-${t.split(" ")[0].toLowerCase()}`}>
              <Icon className="h-6 w-6" style={{ color }} />
              <h3 className="font-display text-xl font-semibold mt-6">{t}</h3>
              <p className="text-sm text-slate-400 mt-3 leading-relaxed">{d}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="how" className="max-w-7xl mx-auto px-6 pb-28 grid lg:grid-cols-[1fr_1.4fr] gap-16">
        <div>
          <h2 className="font-display text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight">Set up in minutes.</h2>
          <p className="mt-4 text-slate-400 flex items-start gap-2"><Hand className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" /> Turn AI off for any chat and reply yourself — the customer never notices.</p>
        </div>
        <div className="space-y-px">
          {STEPS.map(([n, t, d]) => (
            <div key={n} className="flex gap-8 py-7 border-t border-white/10">
              <span className="font-mono text-emerald-400 text-sm pt-1">{n}</span>
              <div><h3 className="font-display text-xl font-semibold">{t}</h3><p className="text-slate-400 mt-2 text-sm">{d}</p></div>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-white/5">
        <div className="max-w-7xl mx-auto px-6 py-16 flex flex-col md:flex-row md:items-end justify-between gap-8">
          <p className="font-display text-4xl sm:text-6xl font-extrabold tracking-tight text-white/90">Reply faster.<br /><span className="text-slate-600">Sell more.</span></p>
          <p className="text-sm text-slate-500">© {new Date().getFullYear()} ReplyFlow</p>
        </div>
      </footer>
    </div>
  );
}
