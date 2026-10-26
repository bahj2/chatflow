import { useState } from "react";
import { Navigate, Link, useLocation } from "react-router-dom";
import { BrandMark, BRAND } from "@/components/Brand";
import { useAuth, errMsg } from "@/lib/auth";
import { Input } from "@/components/ui/input";

export const GoogleIcon = () => (
  <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>
);

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export const googleRedirect = () => {
  const redirectUrl = window.location.origin + "/dashboard";
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
};

export default function Login() {
  const { user, login } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(location.state?.error || "");
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/dashboard" replace />;
  const google = googleRedirect;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grain grid-bg min-h-screen grid place-items-center px-6">
      <form onSubmit={submit} className="rise w-full max-w-sm bg-[#0F1522] border border-white/10 rounded-2xl p-8" data-testid="login-form">
        <Link to="/" className="flex items-center gap-2 font-display font-bold text-lg mb-8">
          <BrandMark />{BRAND}
        </Link>
        <h1 className="font-display text-2xl font-bold">Sign in</h1>
        <p className="text-sm text-slate-400 mt-1 mb-6">Access your inbox and AI settings.</p>
        <div className="space-y-3">
          <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="login-email-input" required />
          <Input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} data-testid="login-password-input" required />
        </div>
        {error && <p className="text-sm text-red-400 mt-3" data-testid="login-error">{error}</p>}
        <button disabled={busy} data-testid="login-submit-btn"
          className="mt-6 w-full rounded-full bg-emerald-500 text-slate-950 py-3 font-semibold hover:bg-emerald-400 transition-colors disabled:opacity-60">
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <div className="flex items-center gap-3 my-5 text-xs text-slate-500"><span className="h-px flex-1 bg-white/10" />or<span className="h-px flex-1 bg-white/10" /></div>
        <button type="button" onClick={google} data-testid="google-login-btn"
          className="w-full rounded-full bg-white text-slate-900 py-3 font-semibold hover:bg-slate-200 transition-colors flex items-center justify-center gap-2.5">
          <GoogleIcon /> Continue with Google
        </button>
        <p className="text-sm text-slate-400 text-center mt-6">New here? <Link to="/signup" className="text-emerald-400 hover:text-emerald-300 font-semibold" data-testid="go-signup-link">Create a business account</Link></p>
      </form>
    </div>
  );
}
