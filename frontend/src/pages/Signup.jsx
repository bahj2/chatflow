import { useState } from "react";
import { Navigate, Link } from "react-router-dom";
import { AuthShell, authCard, googleBtn, Divider } from "@/components/AuthShell";
import { useAuth, errMsg } from "@/lib/auth";
import { Input } from "@/components/ui/input";
import { GoogleIcon, googleRedirect } from "@/pages/Login";

export default function Signup() {
  const { user, register } = useAuth();
  const [form, setForm] = useState({ business_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/dashboard" replace />;
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
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
        <h1 className="font-display text-2xl font-bold">Create your account</h1>
        <p className="text-sm text-muted-foreground mt-1 mb-6">Get your own AI inbox in under a minute.</p>
        <div className="space-y-3">
          <Input placeholder="Business name" value={form.business_name} onChange={set("business_name")} data-testid="signup-business-input" required className="h-11" />
          <Input type="email" placeholder="Email" value={form.email} onChange={set("email")} data-testid="signup-email-input" required className="h-11" />
          <Input type="password" placeholder="Password (min 6 characters)" value={form.password} onChange={set("password")} minLength={6} data-testid="signup-password-input" required className="h-11" />
        </div>
        {error && <p className="text-sm text-red-600 dark:text-red-400 mt-3" data-testid="signup-error">{error}</p>}
        <button disabled={busy} data-testid="signup-submit-btn" className="mt-6 w-full rounded-full btn-brand py-3 font-semibold disabled:opacity-60">
          {busy ? "Creating…" : "Create account"}
        </button>
        <Divider />
        <button type="button" onClick={googleRedirect} data-testid="signup-google-btn" className={googleBtn}>
          <GoogleIcon /> Sign up with Google
        </button>
        <p className="text-sm text-muted-foreground text-center mt-6">Already have an account? <Link to="/login" className="text-primary hover:underline underline-offset-4 font-semibold" data-testid="go-login-link">Sign in</Link></p>
      </form>
    </AuthShell>
  );
}
