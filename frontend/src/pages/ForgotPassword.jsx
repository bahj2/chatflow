import { useEffect, useState } from "react";
import { Navigate, Link } from "react-router-dom";
import { Mail, KeyRound, ArrowRight, ArrowLeft, Loader2, MailCheck } from "lucide-react";
import { AuthShell, authCard } from "@/components/AuthShell";
import { IconInput, PasswordInput, StrengthMeter, SecureNote, pwOk } from "@/components/AuthFields";
import { api, useAuth, errMsg } from "@/lib/auth";

const useCooldown = () => {
  const [left, setLeft] = useState(0);
  useEffect(() => {
    if (!left) return undefined;
    const t = setTimeout(() => setLeft((x) => x - 1), 1000);
    return () => clearTimeout(t);
  }, [left]);
  return [left, () => setLeft(60)];
};

const Submit = ({ busy, children, testid }) => (
  <button disabled={busy} data-testid={testid} className="mt-6 w-full rounded-full btn-brand py-3 font-semibold disabled:opacity-60 inline-flex items-center justify-center gap-2">
    {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}{children}{!busy && <ArrowRight className="h-4 w-4" />}
  </button>
);

export default function ForgotPassword() {
  const { user, setSession } = useAuth();
  const [step, setStep] = useState("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [left, startCooldown] = useCooldown();
  if (user) return <Navigate to="/dashboard" replace />;

  const run = async (fn) => {
    setBusy(true);
    setError("");
    try { await fn(); } catch (e) { setError(errMsg(e)); } finally { setBusy(false); }
  };
  const sendCode = (e) => {
    e?.preventDefault();
    run(async () => { await api.post("/auth/forgot-password", { email }); setStep("code"); startCooldown(); });
  };
  const reset = (e) => {
    e.preventDefault();
    if (code.length !== 6) return setError("Enter the 6-digit code from the email.");
    if (!pwOk(password)) return setError("Please use at least 8 characters with a letter and a number.");
    return run(async () => setSession((await api.post("/auth/reset-password", { email, code, password })).data));
  };

  return (
    <AuthShell eyebrow="Account help" title="Locked out? Get back to your customers in a minute.">
      {step === "email" ? (
        <form onSubmit={sendCode} className={authCard} data-testid="forgot-form">
          <span className="grid h-11 w-11 place-items-center rounded-2xl bg-primary/10 text-primary"><KeyRound className="h-5 w-5" /></span>
          <h1 className="mt-4 font-display text-2xl font-bold tracking-tight">Forgot your password?</h1>
          <p className="text-sm text-muted-foreground mt-1 mb-6">Enter your account email and we&apos;ll send you a 6-digit code.</p>
          <IconInput label="Email" Icon={Mail} type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="forgot-email-input" required autoComplete="email" />
          {error && <p className="text-sm text-red-600 dark:text-red-400 mt-3" data-testid="forgot-error">{error}</p>}
          <Submit busy={busy} testid="forgot-send-btn">Send code</Submit>
          <Link to="/login" className="mt-6 flex items-center justify-center gap-1.5 text-sm font-semibold text-primary hover:underline underline-offset-4" data-testid="forgot-back-login"><ArrowLeft className="h-4 w-4" /> Back to sign in</Link>
          <SecureNote />
        </form>
      ) : (
        <form onSubmit={reset} className={authCard} data-testid="reset-form">
          <span className="grid h-11 w-11 place-items-center rounded-2xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"><MailCheck className="h-5 w-5" /></span>
          <h1 className="mt-4 font-display text-2xl font-bold tracking-tight">Check your email</h1>
          <p className="text-sm text-muted-foreground mt-1 mb-6" data-testid="reset-sent-note">If an account exists for <b className="text-foreground">{email}</b>, we sent a 6-digit code. It works for 15 minutes.</p>
          <div className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold text-foreground/80">6-digit code</span>
              <input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" placeholder="••••••"
                data-testid="reset-code-input" className="h-14 w-full rounded-xl border border-input bg-background text-center font-mono text-2xl tracking-[0.6em] outline-none transition-[border-color,box-shadow] duration-200 focus:border-primary/60 focus:ring-4 focus:ring-primary/10" />
            </label>
            <div>
              <PasswordInput label="New password" testid="reset-password-input" placeholder="At least 8 characters with a number" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} autoComplete="new-password" />
              <StrengthMeter pw={password} />
            </div>
          </div>
          {error && <p className="text-sm text-red-600 dark:text-red-400 mt-3" data-testid="reset-error">{error}</p>}
          <Submit busy={busy} testid="reset-submit-btn">Save new password</Submit>
          <div className="mt-5 flex items-center justify-between text-sm">
            <button type="button" onClick={() => { setStep("email"); setError(""); }} className="text-muted-foreground hover:text-foreground" data-testid="reset-change-email">Change email</button>
            <button type="button" onClick={sendCode} disabled={left > 0 || busy} className="font-semibold text-primary disabled:text-muted-foreground" data-testid="reset-resend-btn">
              {left > 0 ? `Resend code in ${left}s` : "Resend code"}
            </button>
          </div>
          <p className="mt-4 text-center text-[11px] text-muted-foreground">No email? Check your spam folder.</p>
        </form>
      )}
    </AuthShell>
  );
}
