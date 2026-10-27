import { useState } from "react";
import { Navigate, Link } from "react-router-dom";
import { AuthShell, authCard, googleBtn, Divider } from "@/components/AuthShell";
import { useAuth, errMsg } from "@/lib/auth";
import { Store, Mail, ArrowRight, Loader2 } from "lucide-react";
import { IconInput, PasswordInput, StrengthMeter, TrialBadge, SecureNote, pwOk } from "@/components/AuthFields";
import { GoogleIcon, googleRedirect } from "@/pages/Login";
import { FacebookLoginButton } from "@/components/FacebookLoginButton";

export default function Signup() {
  const { user, register } = useAuth();
  const [form, setForm] = useState({ business_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/dashboard" replace />;
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    if (!pwOk(form.password)) return setError("Please use at least 8 characters with a letter and a number.");
    setBusy(true);
    setError("");
    try {
      await register(form);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell eyebrow="Free to start" title="Answer every customer in seconds — on every channel.">
      <form onSubmit={submit} className={authCard} data-testid="signup-form">
        <TrialBadge />
        <h1 className="mt-4 font-display text-2xl font-bold tracking-tight">Create your account</h1>
        <p className="text-sm text-muted-foreground mt-1 mb-6">Set up your AI seller in under a minute.</p>
        <div className="space-y-4">
          <IconInput label="Business name" Icon={Store} placeholder="e.g. Sokha Fashion" value={form.business_name} onChange={set("business_name")} data-testid="signup-business-input" required maxLength={80} autoComplete="organization" />
          <IconInput label="Email" Icon={Mail} type="email" placeholder="you@example.com" value={form.email} onChange={set("email")} data-testid="signup-email-input" required autoComplete="email" />
          <div>
            <PasswordInput testid="signup-password-input" placeholder="At least 8 characters with a number" value={form.password} onChange={set("password")} required minLength={8} autoComplete="new-password" />
            <StrengthMeter pw={form.password} />
          </div>
        </div>
        {error && <p className="text-sm text-red-600 dark:text-red-400 mt-3" data-testid="signup-error">{error}</p>}
        <button disabled={busy} data-testid="signup-submit-btn" className="mt-6 w-full rounded-full btn-brand py-3 font-semibold disabled:opacity-60 inline-flex items-center justify-center gap-2">
          {busy ? <><Loader2 className="h-4 w-4 animate-spin" /> Creating…</> : <>Start free trial <ArrowRight className="h-4 w-4" /></>}
        </button>
        <p className="mt-3 text-center text-[11px] leading-relaxed text-muted-foreground" data-testid="signup-terms-note">
          By creating an account you agree to our <Link to="/terms" className="underline underline-offset-2 hover:text-foreground">Terms</Link> and <Link to="/privacy" className="underline underline-offset-2 hover:text-foreground">Privacy Policy</Link>.
        </p>
        <Divider />
        <div className="space-y-3">
          <FacebookLoginButton label="Sign up with Facebook" onError={setError} testid="signup-facebook-btn" />
          <button type="button" onClick={googleRedirect} data-testid="signup-google-btn" className={googleBtn}>
            <GoogleIcon /> Sign up with Google
          </button>
        </div>
        <p className="text-sm text-muted-foreground text-center mt-6">Already have an account? <Link to="/login" className="text-primary hover:underline underline-offset-4 font-semibold" data-testid="go-login-link">Sign in</Link></p>
        <SecureNote />
      </form>
    </AuthShell>
  );
}
