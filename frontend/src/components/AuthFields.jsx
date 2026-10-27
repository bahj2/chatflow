import { useState } from "react";
import { Eye, EyeOff, ShieldCheck, Gift, Lock } from "lucide-react";

const inputCls = "h-12 w-full rounded-xl border border-input bg-background pl-11 pr-3 text-sm outline-none transition-[border-color,box-shadow] duration-200 placeholder:text-muted-foreground/70 focus:border-primary/60 focus:ring-4 focus:ring-primary/10";

export const IconInput = ({ label, Icon, className = "", ...props }) => (
  <label className="block">
    <span className="mb-1.5 block text-xs font-semibold text-foreground/80">{label}</span>
    <span className="relative block">
      <Icon className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <input className={`${inputCls} ${className}`} {...props} />
    </span>
  </label>
);

export const PasswordInput = ({ label = "Password", testid, ...props }) => {
  const [show, setShow] = useState(false);
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold text-foreground/80">{label}</span>
      <span className="relative block">
        <Lock className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input type={show ? "text" : "password"} className={`${inputCls} pr-11`} data-testid={testid} {...props} />
        <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"} data-testid={`${testid}-toggle`}
          className="absolute right-2 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </span>
    </label>
  );
};

export const pwChecks = (pw) => [
  ["8+ characters", pw.length >= 8],
  ["A letter", /[A-Za-z]/.test(pw)],
  ["A number", /\d/.test(pw)],
];
export const pwOk = (pw) => pwChecks(pw).every(([, ok]) => ok);

const LEVELS = [["Too weak", "bg-red-500", "text-red-600 dark:text-red-400"], ["Weak", "bg-orange-500", "text-orange-600 dark:text-orange-400"],
  ["Good", "bg-amber-500", "text-amber-600 dark:text-amber-400"], ["Strong", "bg-emerald-500", "text-emerald-600 dark:text-emerald-400"]];

const score = (pw) => {
  if (!pwOk(pw)) return pw.length >= 6 ? 1 : 0;
  const extra = [pw.length >= 12, /[A-Z]/.test(pw) && /[a-z]/.test(pw), /[^A-Za-z0-9]/.test(pw)].filter(Boolean).length;
  return extra >= 2 ? 3 : 2;
};

export const StrengthMeter = ({ pw }) => {
  if (!pw) return null;
  const s = score(pw);
  const [label, bar, text] = LEVELS[s];
  return (
    <div className="mt-2.5 space-y-2" data-testid="password-strength">
      <div className="flex items-center gap-3">
        <div className="grid flex-1 grid-cols-4 gap-1.5">
          {[0, 1, 2, 3].map((i) => <span key={i} className={`h-1.5 rounded-full transition-colors duration-300 ${i <= s ? bar : "bg-muted"}`} />)}
        </div>
        <span className={`w-16 text-right text-xs font-semibold ${text}`} data-testid="password-strength-label">{label}</span>
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
        {pwChecks(pw).map(([t, ok]) => <li key={t} className={ok ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}>{ok ? "✓" : "○"} {t}</li>)}
      </ul>
    </div>
  );
};

export const TrialBadge = () => (
  <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-semibold text-primary" data-testid="auth-trial-badge">
    <Gift className="h-3.5 w-3.5" /> 14-day free trial · no payment needed
  </span>
);

export const SecureNote = () => (
  <p className="mt-6 flex items-center justify-center gap-1.5 text-[11px] text-muted-foreground" data-testid="auth-secure-note">
    <ShieldCheck className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" /> Your data is encrypted and private to your business
  </p>
);
