import { useState } from "react";
import { Navigate, Link } from "react-router-dom";
import { Zap, Check } from "lucide-react";
import { useAuth, errMsg } from "@/lib/auth";
import { Input } from "@/components/ui/input";
import { GoogleIcon, googleRedirect } from "@/pages/Login";

const PERKS = ["Your own AI assistant trained on your business", "Telegram, Messenger & website chat", "Private inbox for you and your team"];

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
    <div className="grain grid-bg min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-center px-16 border-r border-white/5">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-emerald-400 mb-6">Free to start</p>
        <h2 className="font-display text-4xl font-extrabold tracking-tight leading-tight max-w-md">Answer every customer in seconds — on every channel.</h2>
        <ul className="mt-10 space-y-4">
          {PERKS.map((p) => <li key={p} className="flex items-center gap-3 text-slate-300"><Check className="h-4 w-4 text-emerald-400" />{p}</li>)}
        </ul>
      </div>
      <div className="grid place-items-center px-6 py-12">
        <form onSubmit={submit} className="rise w-full max-w-sm bg-[#0F1522] border border-white/10 rounded-2xl p-8" data-testid="signup-form">
          <Link to="/" className="flex items-center gap-2 font-display font-bold text-lg mb-8">
            <span className="h-8 w-8 rounded-lg bg-emerald-500 text-slate-950 grid place-items-center"><Zap className="h-4 w-4" /></span>ReplyFlow
          </Link>
          <h1 className="font-display text-2xl font-bold">Create your account</h1>
          <p className="text-sm text-slate-400 mt-1 mb-6">Get your own AI inbox in under a minute.</p>
          <div className="space-y-3">
            <Input placeholder="Business name" value={form.business_name} onChange={set("business_name")} data-testid="signup-business-input" required />
            <Input type="email" placeholder="Email" value={form.email} onChange={set("email")} data-testid="signup-email-input" required />
            <Input type="password" placeholder="Password (min 6 characters)" value={form.password} onChange={set("password")} minLength={6} data-testid="signup-password-input" required />
          </div>
          {error && <p className="text-sm text-red-400 mt-3" data-testid="signup-error">{error}</p>}
          <button disabled={busy} data-testid="signup-submit-btn"
            className="mt-6 w-full rounded-full bg-emerald-500 text-slate-950 py-3 font-semibold hover:bg-emerald-400 transition-colors disabled:opacity-60">
            {busy ? "Creating…" : "Create account"}
          </button>
          <div className="flex items-center gap-3 my-5 text-xs text-slate-500"><span className="h-px flex-1 bg-white/10" />or<span className="h-px flex-1 bg-white/10" /></div>
          <button type="button" onClick={googleRedirect} data-testid="signup-google-btn"
            className="w-full rounded-full bg-white text-slate-900 py-3 font-semibold hover:bg-slate-200 transition-colors flex items-center justify-center gap-2.5">
            <GoogleIcon /> Sign up with Google
          </button>
          <p className="text-sm text-slate-400 text-center mt-6">Already have an account? <Link to="/login" className="text-emerald-400 hover:text-emerald-300 font-semibold" data-testid="go-login-link">Sign in</Link></p>
        </form>
      </div>
    </div>
  );
}
