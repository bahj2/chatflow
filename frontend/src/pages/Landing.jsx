import { Link } from "react-router-dom";
import { ArrowRight, Send, Facebook, QrCode, Brain, Hand, Sparkles, Mic, ImageIcon } from "lucide-react";
import { BrandMark, BRAND } from "@/components/Brand";
import { ThemeToggle } from "@/components/ThemeToggle";
import { TelegramDemo } from "@/components/TelegramDemo";

const FEATURES = [
  { Icon: Send, color: "#229ED9", t: "Telegram bot", d: "Paste your BotFather token, click connect. Every message gets an instant reply.", span: "lg:col-span-2" },
  { Icon: Facebook, color: "#0084FF", t: "Facebook Messenger", d: "Connect your Page and answer customers 24/7 — even while you sleep.", span: "lg:col-span-2" },
  { Icon: Mic, color: "#7C3AED", t: "Khmer voice replies", d: "Customers send a voice note, the AI answers with voice — in the seller’s own cloned voice.", span: "lg:col-span-2" },
  { Icon: QrCode, color: "#E11D48", t: "Bakong KHQR payments", d: "When a customer confirms an order, the AI sends a KHQR with the exact total. Pay with any Cambodian bank app.", span: "lg:col-span-2" },
  { Icon: ImageIcon, color: "#10B981", t: "Product photos", d: "Ask “do you have this?” and the AI replies with the product name, price and photo from your catalog.", span: "lg:col-span-2" },
  { Icon: Brain, color: "#F59E0B", t: "Knows your business", d: "Teach it your products, prices, FAQs and Notion pages once. It understands what clients really mean.", span: "lg:col-span-2" },
];

const STEPS = [
  ["1", "Describe your business", "Shop, services or anything else — add info, FAQs and pick a tone."],
  ["2", "Connect your channels", "Paste your Telegram bot token and connect your Facebook Page — all in one place."],
  ["3", "AI replies, you stay in control", "Take over any chat, or tap an AI-suggested reply to answer in one click."],
];

const Nav = () => (
  <nav className="sticky top-0 z-40 backdrop-blur-xl bg-background/75 border-b border-border/60">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
      <Link to="/" className="flex items-center gap-2 font-display font-bold text-lg" data-testid="nav-logo">
        <BrandMark />
        <span className="hidden min-[400px]:inline">{BRAND}</span>
      </Link>
      <div className="hidden md:flex gap-8 text-sm text-muted-foreground">
        <a href="#features" className="hover:text-foreground transition-colors" data-testid="nav-features-link">Features</a>
        <a href="#how" className="hover:text-foreground transition-colors" data-testid="nav-how-link">How it works</a>
      </div>
      <div className="flex items-center gap-2">
        <ThemeToggle />
        <Link to="/login" data-testid="nav-login-btn" className="px-3 sm:px-4 py-2 text-sm font-semibold text-foreground/80 hover:text-foreground transition-colors">Log in</Link>
        <Link to="/signup" data-testid="nav-signup-btn" className="rounded-full btn-brand px-4 sm:px-5 py-2 text-sm font-semibold">Start free</Link>
      </div>
    </div>
  </nav>
);

const Hero = () => (
  <section className="grid-bg relative overflow-hidden">
    <div className="absolute -top-40 -left-40 h-[520px] w-[520px] brand-glow pointer-events-none" />
    <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-16 sm:pt-20 pb-24 grid lg:grid-cols-[1.15fr_1fr] gap-14 items-start relative">
      <div className="rise lg:pt-20">
        <p className="inline-flex items-center gap-2 rounded-full border border-border bg-card/80 px-3 py-1.5 text-xs font-medium text-muted-foreground mb-7 card-shadow" data-testid="hero-eyebrow">
          <span className="relative flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" /><span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" /></span>
          Telegram · Messenger · Bakong KHQR
        </p>
        <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.05]">
          Every client message,<br />answered in <span className="text-brand">seconds.</span>
        </h1>
        <p className="mt-6 text-base md:text-lg text-muted-foreground max-w-xl leading-relaxed">
          ReplyFlow's AI understands what your customers want and replies instantly on all your channels — in their language, in your tone. Jump in anytime with one-tap suggested replies.
        </p>
        <div className="mt-10 flex flex-wrap gap-3 sm:gap-4">
          <Link to="/signup" data-testid="hero-get-started-btn" className="inline-flex items-center gap-2 rounded-full btn-brand px-7 py-3.5 font-semibold">
            Create free account <ArrowRight className="h-4 w-4" />
          </Link>
          <a href="#how" data-testid="hero-how-btn" className="rounded-full border border-border bg-card/60 px-7 py-3.5 font-semibold hover:bg-muted transition-colors">How it works</a>
        </div>
        <div className="mt-12 grid grid-cols-3 gap-3 max-w-md">
          {[["< 5s", "avg. reply"], ["24/7", "always on"], ["2", "channels"]].map(([a, b]) => (
            <div key={b} className="rounded-2xl border border-border/70 bg-card/70 px-4 py-3 card-shadow" data-testid={`hero-stat-${b.split(" ").pop()}`}>
              <p className="font-display text-2xl font-bold">{a}</p><p className="text-xs text-muted-foreground">{b}</p>
            </div>
          ))}
        </div>
      </div>
      <div className="rise relative" style={{ animationDelay: "0.15s" }}>
        <div className="absolute inset-0 sm:-inset-10 brand-glow pointer-events-none" />
        <p className="relative font-mono text-[11px] uppercase tracking-widest text-muted-foreground mb-3 flex items-center gap-2"><Sparkles className="h-3 w-3 text-primary" /> Real example — a customer on Telegram</p>
        <TelegramDemo className="relative max-w-md mx-auto lg:mx-0" />
      </div>
    </div>
  </section>
);

const Features = () => (
  <section id="features" className="max-w-7xl mx-auto px-4 sm:px-6 py-24">
    <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary mb-4">Features</p>
    <h2 className="font-display text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight max-w-2xl">One AI brain. All the places your clients write to you.</h2>
    <div className="mt-12 grid sm:grid-cols-2 lg:grid-cols-6 gap-4">
      {FEATURES.map(({ Icon, color, t, d, span }, i) => (
        <div key={t} className={`rise group rounded-2xl border border-border bg-card p-7 card-shadow transition-[transform,border-color] duration-300 hover:-translate-y-1 hover:border-primary/40 ${span}`}
          style={{ animationDelay: `${0.05 * i}s` }} data-testid={`feature-${t.split(" ")[0].toLowerCase()}`}>
          <span className="grid h-11 w-11 place-items-center rounded-xl" style={{ background: `${color}1f`, color }}><Icon className="h-5 w-5" /></span>
          <h3 className="font-display text-lg font-semibold mt-5">{t}</h3>
          <p className="text-sm text-muted-foreground mt-2 leading-relaxed max-w-prose">{d}</p>
        </div>
      ))}
    </div>
  </section>
);

const How = () => (
  <section id="how" className="max-w-7xl mx-auto px-4 sm:px-6 pb-24 grid lg:grid-cols-[1fr_1.4fr] gap-12 lg:gap-16">
    <div>
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary mb-4">How it works</p>
      <h2 className="font-display text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight">Set up in minutes.</h2>
      <p className="mt-5 text-muted-foreground flex items-start gap-2 max-w-sm"><Hand className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" /> Turn AI off for any chat and reply yourself — the customer never notices.</p>
    </div>
    <ol className="space-y-3">
      {STEPS.map(([n, t, d]) => (
        <li key={n} className="flex gap-5 rounded-2xl border border-border bg-card p-6 card-shadow" data-testid={`how-step-${n}`}>
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand font-display font-bold text-white">{n}</span>
          <div><h3 className="font-display text-lg font-semibold">{t}</h3><p className="text-muted-foreground mt-1.5 text-sm leading-relaxed">{d}</p></div>
        </li>
      ))}
    </ol>
  </section>
);

const Cta = () => (
  <section className="max-w-7xl mx-auto px-4 sm:px-6 pb-24">
    <div className="relative overflow-hidden rounded-3xl bg-brand px-8 py-14 sm:px-14 text-white">
      <div className="absolute inset-0 opacity-20 grid-bg" style={{ backgroundImage: "linear-gradient(rgba(255,255,255,.25) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.25) 1px, transparent 1px)" }} />
      <div className="relative flex flex-col md:flex-row md:items-center justify-between gap-8">
        <div>
          <h2 className="font-display text-3xl sm:text-4xl font-extrabold tracking-tight">Reply faster. Sell more.</h2>
          <p className="mt-3 text-white/80 max-w-lg">Your AI seller answers Telegram and Messenger in Khmer, sends product photos and collects KHQR payments.</p>
        </div>
        <Link to="/signup" data-testid="cta-signup-btn" className="inline-flex shrink-0 items-center gap-2 rounded-full bg-white px-7 py-3.5 font-semibold text-indigo-700 shadow-lg transition-transform hover:-translate-y-0.5">
          Start free <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  </section>
);

export default function Landing() {
  return (
    <div className="grain min-h-screen bg-background text-foreground overflow-x-hidden">
      <Nav />
      <Hero />
      <Features />
      <How />
      <Cta />
      <footer className="border-t border-border/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2 font-display font-bold"><BrandMark className="h-7 w-7" />{BRAND}</div>
          <p className="text-sm text-muted-foreground" data-testid="footer-copyright">© {new Date().getFullYear()} ReplyFlow</p>
        </div>
      </footer>
    </div>
  );
}
