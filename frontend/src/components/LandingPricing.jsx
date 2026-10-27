import { Link } from "react-router-dom";
import { ArrowRight, Check, Gift, PlayCircle } from "lucide-react";
import { PLAN_FEATURES } from "@/lib/billing";

export const TOUR_VIDEO = "/videos/replyflow-tour.mp4";

const TRIAL = ["14 days free, no payment needed", "200 AI replies", "Pro features: Notion knowledge, 3 logins, products, KHQR", "AI understands voice messages (answers in text)"];
const PLANS = [["starter", "Starter", 10, 1000], ["pro", "Pro", 25, 3000], ["business", "Business", 59, 8000]];

const TrialCard = () => (
  <div className="relative rounded-3xl bg-brand p-7 text-white shadow-xl lg:row-span-1" data-testid="pricing-trial">
    <span className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-xs font-semibold"><Gift className="h-3.5 w-3.5" /> Free trial</span>
    <p className="mt-4 font-display text-4xl font-extrabold">$0<span className="text-base font-medium text-white/80"> / 14 days</span></p>
    <ul className="mt-5 space-y-2">{TRIAL.map((f) => <li key={f} className="flex gap-2 text-sm text-white/90"><Check className="h-4 w-4 shrink-0 mt-0.5" />{f}</li>)}</ul>
    <Link to="/signup" data-testid="pricing-trial-btn" className="mt-7 inline-flex w-full items-center justify-center gap-2 rounded-full bg-white py-3 font-semibold text-indigo-700 transition-transform hover:-translate-y-0.5">
      Start free trial <ArrowRight className="h-4 w-4" />
    </Link>
  </div>
);

const PlanCard = ([key, name, price, replies]) => (
  <div key={key} className={`flex flex-col rounded-3xl border bg-card p-7 card-shadow ${key === "pro" ? "border-primary/60" : "border-border"}`} data-testid={`pricing-plan-${key}`}>
    <p className="font-display text-lg font-semibold">{name}</p>
    <p className="mt-3 font-display text-4xl font-extrabold">${price}<span className="text-base font-medium text-muted-foreground"> / month</span></p>
    <p className="mt-1 text-sm font-semibold text-primary">{replies.toLocaleString()} AI replies / month</p>
    <ul className="mt-5 space-y-2 flex-1">{PLAN_FEATURES[key].map((f) => <li key={f} className="flex gap-2 text-sm text-foreground/80"><Check className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400 mt-0.5" />{f}</li>)}</ul>
  </div>
);

export const Pricing = () => (
  <section id="pricing" className="max-w-7xl mx-auto px-4 sm:px-6 pb-24">
    <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary mb-4">Pricing</p>
    <h2 className="font-display text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight max-w-2xl">Try it free for 14 days. Pay by KHQR only if you love it.</h2>
    <div className="mt-12 grid md:grid-cols-2 lg:grid-cols-4 gap-4">
      <TrialCard />
      {PLANS.map(PlanCard)}
    </div>
    <p className="mt-5 text-xs text-muted-foreground">Voice replies to voice messages and the seller voice clone are in the paid Pro and Business plans.</p>
  </section>
);

export const TourVideo = ({ className = "" }) => (
  <video src={TOUR_VIDEO} controls playsInline preload="metadata" poster="/videos/replyflow-tour.jpg" className={`w-full rounded-2xl bg-black ${className}`} data-testid="tour-video" />
);

export const VideoSection = () => (
  <section id="video" className="max-w-5xl mx-auto px-4 sm:px-6 pb-24">
    <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary mb-4 flex items-center gap-2"><PlayCircle className="h-4 w-4" /> Watch how it works</p>
    <h2 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">See Replyflow AI in 2 minutes</h2>
    <p className="mt-3 text-muted-foreground">A short tour in Khmer: sign up, connect Telegram, add products, test the AI and get paid by KHQR.</p>
    <div className="mt-8 rounded-3xl border border-border bg-card p-2 card-shadow"><TourVideo /></div>
  </section>
);
