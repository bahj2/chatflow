import { Link } from "react-router-dom";
import { Check, Mic, QrCode } from "lucide-react";
import { BrandMark, BRAND } from "@/components/Brand";
import { ThemeToggle } from "@/components/ThemeToggle";

const PERKS = ["Your own AI assistant trained on your business", "Telegram & Facebook Messenger", "Private inbox for you and your team"];

const Showcase = ({ eyebrow, title }) => (
  <div className="relative hidden lg:flex flex-col justify-center overflow-hidden bg-brand px-16 text-white" data-testid="auth-showcase">
    <div className="absolute inset-0 opacity-20" style={{ backgroundImage: "linear-gradient(rgba(255,255,255,.22) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.22) 1px, transparent 1px)", backgroundSize: "48px 48px" }} />
    <div className="absolute -bottom-32 -right-24 h-96 w-96 rounded-full bg-white/10 blur-3xl" />
    <div className="relative max-w-md">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-white/70 mb-6">{eyebrow}</p>
      <h2 className="font-display text-4xl font-extrabold tracking-tight leading-tight">{title}</h2>
      <ul className="mt-10 space-y-4">
        {PERKS.map((p) => (
          <li key={p} className="flex items-center gap-3 text-white/90">
            <span className="grid h-6 w-6 place-items-center rounded-full bg-white/15"><Check className="h-3.5 w-3.5" /></span>{p}
          </li>
        ))}
      </ul>
      <div className="mt-12 space-y-3">
        <div className="w-fit max-w-[85%] rounded-2xl rounded-bl-md bg-white/15 px-4 py-2.5 text-sm backdrop-blur-md">មានអាវយឺតពណ៌សទំហំ M ទេបង?</div>
        <div className="ml-auto flex w-fit items-center gap-2 rounded-2xl rounded-br-md bg-white px-4 py-2.5 text-sm text-indigo-900 shadow-lg">
          <Mic className="h-4 w-4 text-indigo-600" /> ចាស មានបង! $8 · <QrCode className="h-4 w-4 text-rose-600" /> KHQR
        </div>
      </div>
    </div>
  </div>
);

export const AuthShell = ({ eyebrow, title, children }) => (
  <div className="grain min-h-screen grid lg:grid-cols-2 bg-background">
    <Showcase eyebrow={eyebrow} title={title} />
    <div className="grid-bg relative flex flex-col px-6 py-6">
      <div className="flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 font-display font-bold text-lg" data-testid="auth-logo"><BrandMark />{BRAND}</Link>
        <ThemeToggle />
      </div>
      <div className="flex flex-1 items-center justify-center py-10">{children}</div>
    </div>
  </div>
);

export const authCard = "rise w-full max-w-sm rounded-3xl border border-border bg-card p-8 card-shadow";
export const googleBtn = "w-full rounded-full bg-white text-slate-900 py-3 font-semibold border border-border shadow-sm hover:bg-slate-50 transition-colors flex items-center justify-center gap-2.5";
export const Divider = () => <div className="flex items-center gap-3 my-5 text-xs text-muted-foreground"><span className="h-px flex-1 bg-border" />or<span className="h-px flex-1 bg-border" /></div>;
