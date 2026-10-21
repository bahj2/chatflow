import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth, errMsg } from "@/lib/auth";

export default function AuthCallback() {
  const { hash } = useLocation();
  const navigate = useNavigate();
  const { loginGoogle, failGoogle } = useAuth();
  const done = useRef(false);

  useEffect(() => {
    if (done.current) return;
    done.current = true;
    const sid = new URLSearchParams(hash.slice(1)).get("session_id");
    loginGoogle(sid)
      .then(() => navigate("/dashboard", { replace: true }))
      .catch((e) => {
        failGoogle();
        navigate("/login", { replace: true, state: { error: errMsg(e) } });
      });
  }, [hash, loginGoogle, failGoogle, navigate]);

  return <div className="min-h-screen grid place-items-center text-slate-400" data-testid="auth-callback">Signing you in…</div>;
}
