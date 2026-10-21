import { useState } from "react";
import { Navigate, Link } from "react-router-dom";
import { Zap } from "lucide-react";
import { useAuth, errMsg } from "@/lib/auth";
import { Input } from "@/components/ui/input";

export default function Login() {
  const { user, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/dashboard" replace />;

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
          <span className="h-8 w-8 rounded-lg bg-emerald-500 text-slate-950 grid place-items-center"><Zap className="h-4 w-4" /></span>ReplyFlow
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
      </form>
    </div>
  );
}
